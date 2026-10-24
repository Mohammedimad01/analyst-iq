import { ArrowDownRight, ArrowUpRight, Info, Minus } from "lucide-react";

import { formatKpiChange, formatKpiValue } from "@/lib/format";
import type { Kpi } from "@/types/api";

const TONE = {
  positive: "bg-positive-soft text-positive",
  negative: "bg-negative-soft text-negative",
  neutral: "bg-subtle text-ink-2",
} as const;

const SENTIMENT_TEXT = { positive: "favourable", negative: "unfavourable", neutral: "neutral" } as const;

export function KpiCard({ kpi, compact = false }: { kpi: Kpi; compact?: boolean }) {
  const Arrow = kpi.direction === "up" ? ArrowUpRight : kpi.direction === "down" ? ArrowDownRight : Minus;
  const tooltipId = `kpi-def-${kpi.key}`;
  return (
    <div className="group relative rounded-xl border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-ink-3">{kpi.label}</h3>
        <button
          type="button"
          className="peer rounded text-ink-3 hover:text-ink"
          aria-describedby={tooltipId}
          aria-label={`How ${kpi.label} is calculated`}
        >
          <Info className="size-3.5" />
        </button>
        <div
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute right-3 top-9 z-20 w-64 rounded-lg bg-ink px-3 py-2 text-xs leading-relaxed text-white opacity-0 shadow-lg transition-opacity peer-hover:opacity-100 peer-focus-visible:opacity-100"
        >
          {kpi.definition}
        </div>
      </div>
      <p className={`mt-2 font-semibold tracking-tight text-ink ${compact ? "text-xl" : "text-2xl"}`}>
        {formatKpiValue(kpi, kpi.value)}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-medium ${TONE[kpi.sentiment]}`}>
          <Arrow className="size-3" aria-hidden="true" />
          {formatKpiChange(kpi)}
          <span className="sr-only"> ({SENTIMENT_TEXT[kpi.sentiment]})</span>
        </span>
        <span className="text-ink-3">vs {formatKpiValue(kpi, kpi.previous)}</span>
      </div>
    </div>
  );
}
