"use client";

import { HBarChart } from "@/components/charts/HBarChart";
import { AnalyticsGate, PageSkeleton } from "@/components/shell/AnalyticsGate";
import { BreakdownTable } from "@/components/ui/BreakdownTable";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, NoMatchState, RefreshingBadge } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { buildUrl } from "@/lib/api";
import { channelLabel, formatCompactCurrency, formatCurrency, formatDate, formatPercent } from "@/lib/format";
import type { BreakdownPage } from "@/types/api";

function StoresContent({ params }: { params: Record<string, string> }) {
  const stores = useApi<BreakdownPage>(buildUrl("/analytics/breakdown/store", { ...params, limit: 500 }));
  const channels = useApi<BreakdownPage>(buildUrl("/analytics/breakdown/channel", { ...params, limit: 500 }));
  const error = stores.error ?? channels.error;
  if (error) return <ErrorState error={error} onRetry={() => (stores.reload(), channels.reload())} />;
  if (!stores.data || !channels.data) return <PageSkeleton />;
  const refreshing = stores.refreshing || channels.refreshing;
  const { period } = stores.data;

  return (
    <div className={refreshing ? "opacity-70 transition-opacity" : "transition-opacity"}>
      <PageHeader
        title="Stores & Channels"
        description={`${formatDate(period.start_date)} – ${formatDate(period.end_date)} · online and marketplace orders are fulfilled by the E-commerce Hub`}
      >
        <RefreshingBadge show={refreshing} />
      </PageHeader>
      {stores.data.total === 0 ? (
        <NoMatchState />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card title="Net revenue by store">
            <HBarChart
              data={stores.data.items.map((r) => ({ label: r.label, value: r.net_revenue, detail: `${formatPercent(r.share_pct)} of revenue` }))}
              format={(v) => formatCurrency(v)}
              axisFormat={formatCompactCurrency}
              ariaLabel="Net revenue by store"
            />
          </Card>
          <Card title="Gross margin by store">
            <HBarChart
              data={stores.data.items.map((r) => ({ label: r.label, value: r.gross_margin_pct, detail: `${formatCurrency(r.gross_profit)} gross profit` }))}
              format={(v) => formatPercent(v)}
              axisFormat={(v) => `${v}%`}
              ariaLabel="Gross margin by store"
            />
          </Card>
          <Card className="xl:col-span-2" title="Store performance">
            <BreakdownTable rows={stores.data.items} labelHeader="Store" showKey />
          </Card>
          <Card className="xl:col-span-2" title="Channel performance">
            <BreakdownTable rows={channels.data.items} labelHeader="Channel" labelFormat={(r) => channelLabel(r.key)} />
          </Card>
        </div>
      )}
    </div>
  );
}

export default function StoresPage() {
  return <AnalyticsGate>{(params) => <StoresContent params={params} />}</AnalyticsGate>;
}
