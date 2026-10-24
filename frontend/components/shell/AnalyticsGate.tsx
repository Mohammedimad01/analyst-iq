"use client";

import type { ReactNode } from "react";

import { useFilters } from "@/components/shell/FiltersProvider";
import { ErrorState, NoDataState, Skeleton } from "@/components/ui/States";

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

/** Renders children only once the dataset exists and a date range is known. */
export function AnalyticsGate({ children }: { children: (params: Record<string, string>) => ReactNode }) {
  const { options, optionsError, optionsLoading, reloadOptions, params } = useFilters();
  if (optionsError) return <ErrorState error={optionsError} onRetry={reloadOptions} />;
  if (optionsLoading || !options) return <PageSkeleton />;
  if (!options.has_data) return <NoDataState />;
  if (!params) return <PageSkeleton />;
  return <>{children(params)}</>;
}
