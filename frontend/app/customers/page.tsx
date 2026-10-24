"use client";

import { AlertTriangle } from "lucide-react";

import { HBarChart } from "@/components/charts/HBarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import { AnalyticsGate, PageSkeleton } from "@/components/shell/AnalyticsGate";
import { Card, PageHeader } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/KpiCard";
import { ErrorState, NoMatchState, RefreshingBadge } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import { formatCompactCurrency, formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import type { CustomerAnalytics } from "@/types/api";

function CustomersContent({ params }: { params: Record<string, string> }) {
  const { data, error, loading, refreshing, reload } = useApi<CustomerAnalytics>(buildUrl("/analytics/customers", params));
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PageSkeleton />;
  const active = data.kpis.find((k) => k.key === "active_customers")?.value ?? 0;
  const c = data.concentration;

  return (
    <div className={refreshing ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <PageHeader
        title="Customers"
        description={`${formatDate(data.period.start_date)} – ${formatDate(data.period.end_date)} · identified customers only (walk-in orders have no customer ID)`}
      >
        <RefreshingBadge show={refreshing} />
      </PageHeader>

      {data.warnings.length > 0 && (
        <div className="mb-4 space-y-1 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning" role="status">
          {data.warnings.map((w) => (
            <p key={w} className="flex gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {w}
            </p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((k) => (
          <KpiCard key={k.key} kpi={k} />
        ))}
      </div>

      {active === 0 ? (
        <div className="mt-6">
          <NoMatchState />
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2" title="Active and new customers" description={`By ${data.trend.grain}`}>
            <TrendChart
              points={data.trend.points}
              grain={data.trend.grain}
              series={[
                { key: "active_customers", label: "Active customers", color: "var(--color-series-1)" },
                { key: "new_customers", label: "New customers", color: "var(--color-series-2)" },
              ]}
              format={(v) => formatNumber(v)}
              axisFormat={(v) => formatNumber(v)}
            />
          </Card>
          <Card title="Revenue by customer segment">
            <HBarChart
              data={data.segments.map((s) => ({
                label: s.segment,
                value: s.net_revenue,
                detail: `${formatNumber(s.customers)} customers · ${formatPercent(s.share_pct)} of identified revenue`,
              }))}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              labelWidth={90}
              ariaLabel="Net revenue by customer segment"
            />
          </Card>
          <Card
            className="xl:col-span-3"
            title="Top customers"
            description={
              c.share_pct === null
                ? undefined
                : `Concentration: the top ${c.top_fraction_pct}% of customers (${formatNumber(c.top_count)} of ${formatNumber(
                    c.item_count,
                  )}) account for ${formatPercent(c.share_pct)} of identified revenue.`
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-3">
                    <th scope="col" className="py-2 pr-3 font-medium">Customer code</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Orders</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Net revenue</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_customers.map((t) => (
                    <tr key={t.customer_code} className="border-b border-line/70 last:border-0">
                      <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-medium text-ink">{t.customer_code}</th>
                      <td className="tabular py-2 pl-3 text-right text-ink-2">{formatNumber(t.orders)}</td>
                      <td className="tabular py-2 pl-3 text-right text-ink-2">{formatCurrency(t.net_revenue)}</td>
                      <td className="tabular py-2 pl-3 text-right text-ink-2">{formatPercent(t.share_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-ink-3">
              Customers are identified by code only; Analyst IQ stores no names, emails or addresses.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function CustomersPage() {
  return <AnalyticsGate>{(params) => <CustomersContent params={params} />}</AnalyticsGate>;
}
