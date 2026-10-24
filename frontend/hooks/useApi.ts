"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

interface Result<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

/**
 * GET a URL with loading / refreshing / error states. Pass `null` to skip.
 * Previous data stays visible while a new request for the same view is in flight ("refreshing"),
 * but is cleared on error so a failed request never leaves stale numbers looking current.
 */
export function useApi<T>(url: string | null) {
  const [reloadCount, setReloadCount] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  const key = url === null ? null : `${reloadCount}|${url}`;

  useEffect(() => {
    if (url === null || key === null) return;
    const controller = new AbortController();
    apiFetch<T>(url, { signal: controller.signal })
      .then((data) => setResult({ key, data, error: null }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error = err instanceof ApiError ? err : new ApiError("Unexpected error loading data.", 0, "unknown");
        setResult({ key, data: null, error });
      });
    return () => controller.abort();
  }, [url, key]);

  const reload = useCallback(() => setReloadCount((n) => n + 1), []);
  const settled = result !== null && result.key === key;
  const data = result?.data ?? null;
  return {
    data,
    error: settled ? result.error : null,
    loading: key !== null && !settled && data === null,
    refreshing: key !== null && !settled && data !== null,
    reload,
  };
}
