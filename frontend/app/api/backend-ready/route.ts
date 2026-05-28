import { NextResponse } from "next/server";
import { getConfiguredBackendUrl } from "@/lib/backend-url";

const REQUEST_TIMEOUT_MS = 10000;

async function fetchBackend(path: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(`${getConfiguredBackendUrl()}${path}`, {
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET() {
  try {
    const health = await fetchBackend("/health");

    if (health.ok) {
      return NextResponse.json({ status: "ok", source: "health" });
    }

    const root = await fetchBackend("/");

    if (root.status < 500) {
      return NextResponse.json({
        status: "ok",
        source: "root",
        backendStatus: root.status,
      });
    }

    return NextResponse.json(
      {
        status: "warming",
        detail: `LedgerPay API returned ${health.status} from /health`,
      },
      { status: 503 },
    );
  } catch {
    return NextResponse.json(
      {
        status: "warming",
        detail: "LedgerPay API is not reachable yet",
      },
      { status: 503 },
    );
  }
}
