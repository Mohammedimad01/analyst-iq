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

export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
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
