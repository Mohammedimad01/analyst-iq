"use client";

import { HBarChart } from "@/components/charts/HBarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import { AnalyticsGate, PageSkeleton } from "@/components/shell/AnalyticsGate";
import { Card, PageHeader } from "@/components/ui/Card";
import { KpiCard, KpiStrip } from "@/components/ui/KpiCard";
import { ErrorState, NoMatchState, RefreshingBadge } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import {
  channelLabel,
  formatCompactCurrency,
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
} from "@/lib/format";
import type { BreakdownRow, Overview } from "@/types/api";

const PRIMARY = ["net_revenue", "gross_profit", "gross_margin_pct", "orders", "avg_order_value", "units_sold"];
const SECONDARY = ["gross_sales", "discounts", "discount_rate_pct", "return_rate_pct", "cancellation_rate_pct"];

const revenueBars = (rows: BreakdownRow[], label = (r: BreakdownRow) => r.label) =>
  rows.map((r) => ({
    label: label(r),
    value: r.net_revenue,
    detail: `${formatPercent(r.share_pct)} of revenue · ${formatPercent(r.gross_margin_pct)} margin`,
  }));

function OverviewContent({ params }: { params: Record<string, string> }) {
  const { data, error, loading, refreshing, reload } = useApi<Overview>(buildUrl("/dashboard/overview", params));
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PageSkeleton />;

  const kpis = Object.fromEntries(data.kpis.map((k) => [k.key, k]));
  const cmp = data.comparison_period;
  const hasSales = (kpis.orders?.value ?? 0) > 0;

  return (
    <div className={refreshing ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <PageHeader
        title="Overview"
        description={`${formatDate(data.period.start_date)} – ${formatDate(data.period.end_date)} · compared with ${formatDate(
          cmp.start_date,
        )} – ${formatDate(cmp.end_date)} (previous ${cmp.days} days)`}
      >
        <RefreshingBadge show={refreshing} />
      </PageHeader>

      <KpiStrip>{PRIMARY.map((key) => kpis[key] && <KpiCard key={key} kpi={kpis[key]} />)}</KpiStrip>
      <div className="mt-3">
        <KpiStrip columns="xl:grid-cols-5">
          {SECONDARY.map((key) => kpis[key] && <KpiCard key={key} kpi={kpis[key]} compact />)}
        </KpiStrip>
      </div>

      {!hasSales ? (
        <div className="mt-6">
          <NoMatchState />
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card
            className="xl:col-span-2"
            title="Net revenue and gross profit"
            description={`Completed orders, by ${data.trend.grain}`}
          >
            <TrendChart
              points={data.trend.points}
              grain={data.trend.grain}
              series={[
                { key: "net_revenue", label: "Net revenue", color: "var(--color-series-1)" },
                { key: "gross_profit", label: "Gross profit", color: "var(--color-series-2)" },
              ]}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
            />
          </Card>
          <Card title="Revenue by channel" description="Share of net revenue">
            <HBarChart
              data={revenueBars(data.by_channel, (r) => channelLabel(r.key))}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              labelWidth={90}
              ariaLabel="Net revenue by sales channel"
            />
          </Card>

          <Card className="xl:col-span-2" title="Order volume" description={`Completed orders, by ${data.trend.grain}`}>
            <TrendChart
              kind="bar"
              height={200}
              points={data.trend.points}
              grain={data.trend.grain}
              series={[{ key: "orders", label: "Orders", color: "var(--color-series-1)" }]}
              format={(v) => `${formatNumber(v)} orders`}
              axisFormat={(v) => formatNumber(v)}
            />
          </Card>
          <Card title="Revenue by store">
            <HBarChart
              data={revenueBars(data.by_store)}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              ariaLabel="Net revenue by store"
            />
          </Card>

          <Card title="Top products by revenue" description="Top 10 by net revenue">
            <HBarChart
              data={revenueBars(data.top_products)}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              labelWidth={170}
              ariaLabel="Top ten products by net revenue"
            />
          </Card>
          <Card title="Revenue by category">
            <HBarChart
              data={revenueBars(data.by_category)}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              ariaLabel="Net revenue by product category"
            />
          </Card>
          <Card title="Gross margin by category" description="Gross profit ÷ net revenue">
            <HBarChart
              data={[...data.by_category]
                .sort((a, b) => (b.gross_margin_pct ?? -Infinity) - (a.gross_margin_pct ?? -Infinity))
                .map((r) => ({
                  label: r.label,
                  value: r.gross_margin_pct,
                  detail: `${formatCurrency(r.gross_profit)} profit on ${formatCurrency(r.net_revenue)}`,
                }))}
              format={(v) => formatPercent(v)}
              axisFormat={(v) => `${v}%`}
              ariaLabel="Gross margin percentage by product category"
            />
          </Card>
        </div>
      )}
    </div>
  );
}

export default function OverviewPage() {
  return <AnalyticsGate>{(params) => <OverviewContent params={params} />}</AnalyticsGate>;
}
