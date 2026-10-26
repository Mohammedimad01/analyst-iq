import type { ApiErrorBody } from "@/types/api";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

export type QueryValue = string | number | undefined | null | readonly string[];

export function buildUrl(path: string, params: Record<string, QueryValue> = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (typeof value === "object") value.forEach((v) => search.append(key, v));
    else search.append(key, String(value));
  }
  const qs = search.toString();
  return `${API_URL}/api/v1${path}${qs ? `?${qs}` : ""}`;
}

// The free-tier API sleeps when idle and takes up to about a minute to wake; Render's proxy may answer 502-504
// meanwhile. Reads wait longer and retry; writes never retry, so nothing is ever submitted twice.
const READ_TIMEOUT_MS = 60_000;
const READ_ATTEMPTS = 3;
const RETRY_STATUSES = new Set([502, 503, 504]);

function wait(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => (clearTimeout(t), reject(signal.reason)), { once: true });
  });
}

export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const isRead = (init.method ?? "GET").toUpperCase() === "GET";
  for (let attempt = 1; ; attempt++) {
    try {
      return await fetchOnce<T>(url, init, isRead ? READ_TIMEOUT_MS : TIMEOUT_MS);
    } catch (err) {
      const transient =
        err instanceof ApiError && (err.code === "timeout" || err.code === "network_error" || RETRY_STATUSES.has(err.status));
      if (!isRead || !transient || attempt >= READ_ATTEMPTS) throw err;
      await wait(2_000 * attempt, init.signal);
    }
  }
}

async function fetchOnce<T>(url: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (err instanceof DOMException && err.name === "TimeoutError")
      throw new ApiError("The server took too long to respond.", 0, "timeout");
    throw new ApiError(`Cannot reach the Analyst IQ API at ${API_URL}. Is the backend running?`, 0, "network_error");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const err = (body as ApiErrorBody | null)?.error;
    throw new ApiError(err?.message ?? `Request failed (${response.status}).`, response.status, err?.code ?? "error");
  }
  return body as T;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(buildUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
