import { AlertTriangle, DatabaseZap, FilterX, Loader2, RotateCw, Upload } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { ApiError } from "@/lib/api";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-line/70 ${className}`} aria-hidden="true" />;
}

function StateBox({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-line bg-surface px-6 py-14 text-center">
      <div className="text-ink-3">{icon}</div>
      <p className="font-serif text-lg font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const isDb = error.code === "database_unavailable";
  return (
    <div role="alert">
      <StateBox
        icon={isDb ? <DatabaseZap className="size-6 text-negative" /> : <AlertTriangle className="size-6 text-negative" />}
        title={isDb ? "Database unavailable" : "Could not load this data"}
      >
        <p>{error.message}</p>
        <p className="mt-1 text-xs text-ink-3">No figures are shown because none could be verified.</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-subtle"
          >
            <RotateCw className="size-3.5" /> Try again
          </button>
        )}
      </StateBox>
    </div>
  );
}

export function NoDataState() {
  return (
    <StateBox icon={<Upload className="size-6" />} title="No sales data yet">
      <p>Import a CSV or Excel file, or load the synthetic demo dataset, to see your dashboard.</p>
      <Link
        href="/data"
        className="mt-3 inline-flex rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-on-primary hover:bg-primary-hover"
      >
        Go to Data Sources
      </Link>
    </StateBox>
  );
}

export function NoMatchState() {
  return (
    <StateBox icon={<FilterX className="size-6" />} title="No sales match these filters">
      <p>There are no completed orders for this date range and selection. Widen the range or clear a filter.</p>
    </StateBox>
  );
}

export function EmptyChart({ message = "No data for this selection." }: { message?: string }) {
  return <div className="flex h-full min-h-40 items-center justify-center text-sm text-ink-3">{message}</div>;
}

export function RefreshingBadge({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-3" role="status">
      <Loader2 className="size-3.5 animate-spin" /> Updating…
    </span>
  );
}
