"use client";

import { useState } from "react";

import { AnalyticsGate, PageSkeleton } from "@/components/shell/AnalyticsGate";
import { BreakdownTable } from "@/components/ui/BreakdownTable";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, NoMatchState, RefreshingBadge } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { BreakdownPage, SortKey } from "@/types/api";

const PAGE_SIZE = 25;

function ProductsContent({ params }: { params: Record<string, string> }) {
  const [sort, setSort] = useState<SortKey>("net_revenue");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, refreshing, reload } = useApi<BreakdownPage>(
    buildUrl("/analytics/breakdown/product", { ...params, sort, order, limit: PAGE_SIZE, offset }),
  );

  const onSort = (key: SortKey) => {
    if (key === sort) setOrder(order === "desc" ? "asc" : "desc");
    else {
      setSort(key);
      setOrder("desc");
    }
    setOffset(0);
  };

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PageSkeleton />;

  return (
    <div className={refreshing ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <PageHeader
        title="Products"
        description={`${formatDate(data.period.start_date)} – ${formatDate(data.period.end_date)} · ${data.total} products with completed sales`}
      >
        <RefreshingBadge show={refreshing} />
      </PageHeader>
      {data.total === 0 ? (
        <NoMatchState />
      ) : (
        <Card
          title="Product performance"
          description="Click a column to sort. Low-margin and low-volume products are easiest to spot by sorting ascending."
        >
          <BreakdownTable rows={data.items} labelHeader="Product" showKey sort={sort} order={order} onSort={onSort} />
          <div className="mt-4 flex items-center justify-between text-sm text-ink-2">
            <span className="tabular">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <button
                className="rounded-md border border-line-strong px-3 py-1 hover:bg-subtle disabled:opacity-40"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </button>
              <button
                className="rounded-md border border-line-strong px-3 py-1 hover:bg-subtle disabled:opacity-40"
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function ProductsPage() {
  return <AnalyticsGate>{(params) => <ProductsContent key={JSON.stringify(params)} params={params} />}</AnalyticsGate>;
}
