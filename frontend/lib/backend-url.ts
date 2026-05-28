const LOCAL_BACKEND_URL = "http://localhost:8000";
const PRODUCTION_BACKEND_URL = "https://ledgerpay-yt2f.onrender.com";

export function normalizeBackendUrl(value: string | undefined | null) {
  const trimmed = value?.trim();

  if (!trimmed) {
    return null;
  }

  return trimmed
    .replace(/\/+$/, "")
    .replace(/\/health$/, "")
    .replace(/\/v1$/, "");
}

export function getConfiguredBackendUrl() {
  return (
    normalizeBackendUrl(process.env.NEXT_PUBLIC_API_URL) ??
    (process.env.NODE_ENV === "production"
      ? PRODUCTION_BACKEND_URL
      : LOCAL_BACKEND_URL)
  );
}
