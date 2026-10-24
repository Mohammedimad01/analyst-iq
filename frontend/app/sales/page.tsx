"use client";

import { useState } from "react";

import { HBarChart } from "@/components/charts/HBarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import { AnalyticsGate, PageSkeleton } from "@/components/shell/AnalyticsGate";
import { BreakdownTable } from "@/components/ui/BreakdownTable";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, NoMatchState, RefreshingBadge } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import { channelLabel, formatCompactCurrency, formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import type { Grain, SalesAnalytics } from "@/types/api";

const GRAINS: { value: Grain | ""; label: string }[] = [
  { value: "", label: "Auto" },
  { value: "day", label: "Daily" },
  { value: "week", label: "Weekly" },
  { value: "month", label: "Monthly" },
];

function SalesContent({ params }: { params: Record<string, string> }) {
  const [grain, setGrain] = useState<Grain | "">("");
  const { data, error, loading, refreshing, reload } = useApi<SalesAnalytics>(
    buildUrl("/analytics/sales", { ...params, grain }),
  );
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PageSkeleton />;
  const empty = data.trend.points.every((p) => p.orders === 0);

  return (
    <div className={refreshing ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <PageHeader
        title="Sales Analytics"
        description={`${formatDate(data.period.start_date)} – ${formatDate(data.period.end_date)} · completed orders only`}
      >
        <div className="flex items-center gap-3">
          <RefreshingBadge show={refreshing} />
          <div className="inline-flex rounded-lg border border-line-strong bg-surface p-0.5" role="group" aria-label="Time grain">
            {GRAINS.map((g) => (
              <button
                key={g.value}
                onClick={() => setGrain(g.value)}
                aria-pressed={grain === g.value}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  grain === g.value ? "bg-primary text-white" : "text-ink-2 hover:text-ink"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
      </PageHeader>

      {empty ? (
        <NoMatchState />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card className="xl:col-span-2" title="Net revenue and gross profit" description={`By ${data.trend.grain}`}>
            <TrendChart
              points={data.trend.points}
              grain={data.trend.grain}
              series={[
                { key: "net_revenue", label: "Net revenue", color: "var(--color-series-1)" },
                { key: "gross_profit", label: "Gross profit", color: "var(--color-series-2)" },
              ]}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              height={300}
            />
          </Card>
          <Card title="Orders" description={`Completed orders by ${data.trend.grain}`}>
            <TrendChart
              kind="bar"
              height={220}
              points={data.trend.points}
              grain={data.trend.grain}
              series={[{ key: "orders", label: "Orders", color: "var(--color-series-1)" }]}
              format={(v) => `${formatNumber(v)} orders`}
              axisFormat={(v) => formatNumber(v)}
            />
          </Card>
          <Card title="Units sold" description={`By ${data.trend.grain}`}>
            <TrendChart
              kind="bar"
              height={220}
              points={data.trend.points}
              grain={data.trend.grain}
              series={[{ key: "units", label: "Units", color: "var(--color-series-1)" }]}
              format={(v) => `${formatNumber(v)} units`}
              axisFormat={(v) => formatNumber(v)}
            />
          </Card>
          <Card className="xl:col-span-2" title="By category">
            <BreakdownTable rows={data.by_category} labelHeader="Category" />
          </Card>
          <Card title="Revenue by channel">
            <HBarChart
              data={data.by_channel.map((r) => ({
                label: channelLabel(r.key),
                value: r.net_revenue,
                detail: `${formatPercent(r.share_pct)} of revenue`,
              }))}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              labelWidth={90}
              ariaLabel="Net revenue by channel"
            />
          </Card>
          <Card title="By channel">
            <BreakdownTable rows={data.by_channel} labelHeader="Channel" labelFormat={(r) => channelLabel(r.key)} />
          </Card>
        </div>
      )}
    </div>
  );
}

export default function SalesPage() {
  return <AnalyticsGate>{(params) => <SalesContent params={params} />}</AnalyticsGate>;
}
