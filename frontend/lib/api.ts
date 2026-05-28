export type PaymentStatus =
  | "CREATED"
  | "PROCESSING"
  | "SUCCEEDED"
  | "FAILED"
  | "TIMED_OUT";

export type PaymentIntent = {
  id: string;
  merchant_id: string;
  amount: number;
  currency: "usd";
  status: PaymentStatus;
  failure_reason: "insufficient_funds" | "bank_timeout" | null;
  created_at: string;
  updated_at: string;
};

export type LedgerBalance = {
  merchant_id: string;
  balance: number;
  currency: "usd";
  total_received: number;
};

export type LedgerEntry = {
  id: string;
  payment_intent_id: string;
  entry_type: "DEBIT" | "CREDIT";
  account_type: "CUSTOMER" | "MERCHANT";
  amount: number;
  currency: "usd";
  created_at: string;
};

export type Merchant = {
  id: string;
  name: string;
  email: string;
  webhook_url: string | null;
  is_active?: boolean;
  created_at: string;
};

export type RegisterPayload = {
  name: string;
  email: string;
  webhook_url?: string;
};

export type RegisterResponse = Merchant & {
  api_key: string;
};

export type HealthResponse = {
  status: string;
  version: string;
};

export type BackendReadyOptions = {
  timeoutMs?: number;
};

type RequestOptions = {
  auth?: boolean;
  body?: unknown;
  headers?: HeadersInit;
  method?: string;
};

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(detail: string, status: number) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const CONFIGURED_API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export const STORAGE_KEYS = {
  apiKey: "ledgerpay_api_key",
  merchant: "ledgerpay_merchant",
} as const;

// Always call the backend directly — CORS is configured on the server,
// so the browser can reach Render without a Next.js proxy in the middle.
function getApiBaseUrl() {
  return CONFIGURED_API_URL;
}

function getApiKey() {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem(STORAGE_KEYS.apiKey);
}

function createIdempotencyKey() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.removeItem(STORAGE_KEYS.apiKey);
  localStorage.removeItem(STORAGE_KEYS.merchant);
}

export function saveSession(merchant: RegisterResponse) {
  const { api_key: _apiKey, ...profile } = merchant;

  localStorage.setItem(STORAGE_KEYS.apiKey, merchant.api_key);
  localStorage.setItem(STORAGE_KEYS.merchant, JSON.stringify(profile));
}

export function signOut() {
  clearStoredSession();
}

export function getStoredMerchant(): Merchant | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = localStorage.getItem(STORAGE_KEYS.merchant);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as Merchant;
  } catch {
    localStorage.removeItem(STORAGE_KEYS.merchant);
    return null;
  }
}

export function hasApiKey() {
  return Boolean(getApiKey());
}

async function getErrorDetail(response: Response) {
  const fallback = `Request failed with status ${response.status}`;

  try {
    const payload = await response.json();

    if (typeof payload?.detail === "string") {
      return payload.detail;
    }

    if (payload?.detail) {
      return JSON.stringify(payload.detail);
    }

    return fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(path: string, options: RequestOptions = {}) {
  const headers = new Headers(options.headers);
  const apiKey = getApiKey();
  const isJsonBody = options.body !== undefined;

  if (isJsonBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (options.auth !== false && apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: isJsonBody ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  if (response.status === 401) {
    clearStoredSession();

    if (typeof window !== "undefined") {
      window.location.href = "/register";
    }
  }

  if (!response.ok) {
    throw new ApiError(await getErrorDetail(response), response.status);
  }

  return response.json() as Promise<T>;
}

export function registerMerchant(data: RegisterPayload) {
  return request<RegisterResponse>("/v1/merchants", {
    method: "POST",
    auth: false,
    body: {
      ...data,
      webhook_url: data.webhook_url?.trim() || undefined,
    },
  });
}

export function getMe() {
  return request<Merchant>("/v1/merchants/me");
}

export function createPaymentIntent(amount: number, currency = "usd") {
  return request<PaymentIntent>("/v1/payment-intents", {
    method: "POST",
    headers: {
      "Idempotency-Key": createIdempotencyKey(),
    },
    body: { amount, currency },
  });
}

export function confirmPaymentIntent(id: string) {
  return request<PaymentIntent>(`/v1/payment-intents/${id}/confirm`, {
    method: "POST",
    headers: {
      "Idempotency-Key": createIdempotencyKey(),
    },
  });
}

export function listPaymentIntents(limit = 20, offset = 0) {
  return request<PaymentIntent[]>(
    `/v1/payment-intents?limit=${limit}&offset=${offset}`,
  );
}

export function getBalance() {
  return request<LedgerBalance>("/v1/ledger/balance?currency=usd");
}

export function getLedgerEntries(limit = 50, offset = 0) {
  return request<LedgerEntry[]>(
    `/v1/ledger/entries?limit=${limit}&offset=${offset}`,
  );
}

export async function checkBackendReady(
  options: BackendReadyOptions = {},
): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 12000);

  try {
    const response = await fetch("/api/backend/health", {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(
        `Health check failed with status ${response.status}`,
        response.status,
      );
    }

    return response.json() as Promise<HealthResponse>;
  } finally {
    clearTimeout(timeout);
  }
}
