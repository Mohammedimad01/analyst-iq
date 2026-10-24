import { AlertOctagon, AlertTriangle, Info, Sparkles, TrendingDown, TrendingUp } from "lucide-react";

import { formatDate, formatNumber } from "@/lib/format";
import type { Anomaly, Severity } from "@/types/api";

// Status colours always come with an icon and a text label, never colour alone.
export const SEVERITY: Record<Severity, { label: string; className: string; Icon: typeof Info }> = {
  high: { label: "High", className: "bg-negative-soft text-negative", Icon: AlertOctagon },
  medium: { label: "Medium", className: "bg-warning-soft text-warning", Icon: AlertTriangle },
  low: { label: "Low", className: "bg-subtle text-ink-2", Icon: Info },
};

const DIMENSION_LABEL = { store: "Store", channel: "Channel", category: "Category", product: "Product", total: "Business" };

function formatValue(a: Anomaly, v: number): string {
  if (a.metric.endsWith("_pct")) return `${v.toFixed(1)}%`;
  if (a.metric === "net_revenue") return `$${formatNumber(v)}`;
  return formatNumber(Math.round(v * 10) / 10);
}

function change(a: Anomaly): string {
  if (a.metric.endsWith("_pct")) return `${a.abs_diff > 0 ? "+" : ""}${a.abs_diff.toFixed(1)} pp`;
  return a.pct_diff === null ? "" : `${a.pct_diff > 0 ? "+" : ""}${a.pct_diff.toFixed(0)}%`;
}

export function AnomalyItem({
  anomaly: a,
  onExplain,
  explainDisabled,
  explaining,
}: {
  anomaly: Anomaly;
  onExplain: () => void;
  explainDisabled: string | null;
  explaining: boolean;
}) {
  const { label, className, Icon } = SEVERITY[a.severity];
  const Trend = a.direction === "up" ? TrendingUp : TrendingDown;
  const period = a.period_start === a.period_end ? formatDate(a.period_start) : `${formatDate(a.period_start)} – ${formatDate(a.period_end)}`;
  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
          <Icon className="size-3" aria-hidden="true" /> {label}
        </span>
        <span className="text-sm font-medium text-ink">
          {DIMENSION_LABEL[a.dimension]}: {a.segment_label}
        </span>
        <span className="text-xs text-ink-3">· {a.metric_label}</span>
      </div>
      <p className="mt-1.5 flex items-center gap-1.5 text-sm text-ink-2">
        <Trend className="size-4 text-ink-3" aria-hidden="true" />
        <span className="tabular font-semibold text-ink">{formatValue(a, a.observed)}</span>
        vs <span className="tabular">{formatValue(a, a.expected)}</span> expected
        <span className="tabular font-medium text-ink">({change(a)})</span>
      </p>
      <p className="mt-0.5 text-xs text-ink-3">{period}</p>
      <details className="mt-1.5 text-xs text-ink-3">
        <summary className="cursor-pointer">How this was detected</summary>
        <p className="mt-1">{a.method}</p>
        {a.z_score !== null && <p className="mt-0.5">z-score: {a.z_score}</p>}
        <p className="mt-0.5 italic">{a.note}</p>
      </details>
      <button
        onClick={onExplain}
        disabled={explainDisabled !== null || explaining}
        title={explainDisabled ?? undefined}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-line-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Sparkles className="size-3.5" aria-hidden="true" />
        {explaining ? "Explaining…" : "Explain with AI"}
      </button>
    </li>
  );
}
