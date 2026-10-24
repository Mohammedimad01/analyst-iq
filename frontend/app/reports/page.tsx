"use client";

import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { useState } from "react";

import { AnalyticsGate } from "@/components/shell/AnalyticsGate";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { ApiError, buildUrl, postJson } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ReportList, ReportSummary, ReportType } from "@/types/api";

const TYPES: { value: ReportType; label: string; description: string }[] = [
  { value: "executive", label: "Executive summary", description: "KPIs, trend, category/store/channel and anomalies" },
  { value: "sales", label: "Sales performance", description: "KPIs, trend, categories and channels" },
  { value: "product", label: "Product performance", description: "Every product with revenue, profit and margin" },
  { value: "store", label: "Store & channel", description: "Stores and sales channels" },
  { value: "customer", label: "Customer analytics", description: "Customer KPIs, segments, top customers" },
  { value: "profitability", label: "Profitability", description: "Margins by category and lowest-margin products" },
];

const EXPORTS = [
  ["kpis", "Key metrics"],
  ["trend", "Trend"],
  ["categories", "Categories"],
  ["products", "Products"],
  ["stores", "Stores"],
  ["channels", "Channels"],
  ["customers", "Top customers"],
  ["customer-segments", "Customer segments"],
  ["anomalies", "Anomalies"],
] as const;

const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function filterBody(params: Record<string, string>) {
  const list = (v: string) => (v ? [v] : []);
  return { start_date: params.start_date, end_date: params.end_date, store: list(params.store), category: list(params.category), channel: list(params.channel) };
}

function ReportHistory() {
  const list = useApi<ReportList>(buildUrl("/reports", { limit: 20 }));
  if (list.error) return <ErrorState error={list.error} onRetry={list.reload} />;
  if (!list.data) return <Skeleton className="h-32" />;
  if (list.data.items.length === 0) return <p className="py-6 text-center text-sm text-ink-3">No reports generated yet.</p>;
  return (
    <ul className="divide-y divide-line">
      {list.data.items.map((r: ReportSummary) => (
        <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-medium text-ink">
              {r.file_format === "pdf" ? <FileText className="size-4 text-ink-3" /> : <FileSpreadsheet className="size-4 text-ink-3" />}
              {r.title}
              {r.contains_synthetic && <span className="rounded-full bg-warning-soft px-1.5 py-0.5 text-[10px] font-medium text-warning">synthetic</span>}
              {r.requested_by === "automation" && <span className="rounded-full bg-subtle px-1.5 py-0.5 text-[10px] text-ink-2">scheduled</span>}
            </p>
            <p className="text-xs text-ink-3">
              {String(r.params.start_date)} to {String(r.params.end_date)} · {dateTime.format(new Date(r.created_at))} · {(r.size_bytes / 1024).toFixed(0)} KB
            </p>
          </div>
          <a
            href={buildUrl(`/reports/${r.id}/download`)}
            className="inline-flex items-center gap-1.5 rounded-md border border-line-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-subtle"
          >
            <Download className="size-3.5" aria-hidden="true" /> Download {r.file_format.toUpperCase()}
          </a>
        </li>
      ))}
    </ul>
  );
}

function ReportsContent({ params }: { params: Record<string, string> }) {
  const [type, setType] = useState<ReportType>("executive");
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [created, setCreated] = useState<ReportSummary | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      setCreated(await postJson<ReportSummary>("/reports/generate", { type, format, ...filterBody(params) }));
      setHistoryKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("Report generation failed.", 0, "unknown"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Reports"
        description={`Management reports and CSV exports for ${formatDate(params.start_date)} – ${formatDate(params.end_date)} and the current filters. Numbers come from the same calculations as the dashboard.`}
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Generate a report">
          <fieldset>
            <legend className="sr-only">Report type</legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {TYPES.map((t) => (
                <label
                  key={t.value}
                  className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${type === t.value ? "border-primary bg-primary-soft" : "border-line hover:border-line-strong"}`}
                >
                  <input type="radio" name="report-type" value={t.value} checked={type === t.value} onChange={() => setType(t.value)} className="sr-only" />
                  <span className="font-medium text-ink">{t.label}</span>
                  <span className="block text-xs text-ink-3">{t.description}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-lg border border-line-strong p-0.5" role="group" aria-label="File format">
              {(["pdf", "csv"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  aria-pressed={format === f}
                  className={`rounded-md px-3 py-1 text-xs font-medium ${format === f ? "bg-primary text-white" : "text-ink-2 hover:text-ink"}`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
            <button
              onClick={generate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60"
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {busy ? "Generating…" : "Generate report"}
            </button>
          </div>
          {error && (
            <p className="mt-3 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative" role="alert">
              {error.message}
            </p>
          )}
          {created && !error && (
            <p className="mt-3 rounded-md bg-positive-soft px-3 py-2 text-sm text-positive" role="status">
              Created “{created.title}”.{" "}
              <a className="font-medium underline" href={buildUrl(`/reports/${created.id}/download`)}>
                Download {created.file_format.toUpperCase()}
              </a>
            </p>
          )}
          <p className="mt-4 text-xs text-ink-3">
            Reports from synthetic demo data say so on the first page. PDF reports contain tables only; charts stay in the dashboard.
          </p>
        </Card>

        <Card title="Export a table as CSV" description="Raw numbers for spreadsheets. Text that could run as a formula is neutralised.">
          <div className="flex flex-wrap gap-2">
            {EXPORTS.map(([dataset, label]) => (
              <a
                key={dataset}
                href={buildUrl(`/exports/${dataset}.csv`, params)}
                className="inline-flex items-center gap-1.5 rounded-md border border-line-strong px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-subtle"
              >
                <Download className="size-3.5" aria-hidden="true" /> {label}
              </a>
            ))}
          </div>
        </Card>

        <Card className="xl:col-span-2" title="Generated reports">
          <ReportHistory key={historyKey} />
        </Card>
      </div>
    </>
  );
}

export default function ReportsPage() {
  return <AnalyticsGate>{(params) => <ReportsContent params={params} />}</AnalyticsGate>;
}
