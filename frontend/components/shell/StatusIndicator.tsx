"use client";

import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import type { Health } from "@/types/api";

/** Real API/database status from /health, checked once per page load (no polling). */
export function StatusIndicator() {
  const { data, error, loading } = useApi<Health>(buildUrl("/health"));
  let tone = "bg-line-strong";
  let text = "Checking API…";
  if (error) {
    tone = "bg-negative";
    text = "API unreachable";
  } else if (data) {
    tone = data.status === "ok" ? "bg-positive" : "bg-warning";
    text = data.status === "ok" ? `Connected · ${data.database_backend === "postgresql" ? "PostgreSQL" : "SQLite (local)"}` : "Database unavailable";
  }
  return (
    <span className="inline-flex items-center gap-2 text-xs text-ink-2" role="status" title={loading ? undefined : text}>
      <span className={`size-2 rounded-full ${tone}`} aria-hidden="true" />
      <span className="hidden sm:inline">{text}</span>
    </span>
  );
}
