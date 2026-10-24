import { ArrowDownRight, ArrowUpRight, Info, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { formatKpiChange, formatKpiValue } from "@/lib/format";
import type { Kpi } from "@/types/api";

const TONE = {
  positive: "text-positive",
  negative: "text-negative",
  neutral: "text-ink-3",
} as const;

const SENTIMENT_TEXT = { positive: "favourable", negative: "unfavourable", neutral: "neutral" } as const;

/** One ruled strip of KPI cells (1px rules come from the gap over the line-coloured background). */
export function KpiStrip({ children, columns = "xl:grid-cols-6" }: { children: ReactNode; columns?: string }) {
  return (
    <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-3 ${columns}`}>
      {children}
    </div>
  );
}

export function KpiCard({ kpi, compact = false }: { kpi: Kpi; compact?: boolean }) {
  const Arrow = kpi.direction === "up" ? ArrowUpRight : kpi.direction === "down" ? ArrowDownRight : Minus;
  const tooltipId = `kpi-def-${kpi.key}`;
  return (
    <div className={`group relative bg-surface ${compact ? "px-4 py-3" : "px-5 py-4"}`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[12.5px] font-medium text-ink-2">{kpi.label}</h3>
        <button
          type="button"
          className="peer rounded text-ink-3 opacity-60 hover:text-ink hover:opacity-100 focus-visible:opacity-100"
          aria-describedby={tooltipId}
          aria-label={`How ${kpi.label} is calculated`}
        >
          <Info className="size-3.5" />
        </button>
        <div
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute right-3 top-9 z-20 w-64 rounded-md bg-tooltip px-3 py-2 text-xs leading-relaxed text-on-tooltip opacity-0 shadow-[0_8px_24px_-8px_rgba(0,0,0,0.35)] transition-opacity peer-hover:opacity-100 peer-focus-visible:opacity-100"
        >
          {kpi.definition}
        </div>
      </div>
      <p className={`figure mt-1.5 font-medium leading-none text-ink ${compact ? "text-[24px]" : "text-[32px]"}`}>
        {formatKpiValue(kpi, kpi.value)}
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span className={`tabular inline-flex items-center gap-0.5 font-medium ${TONE[kpi.sentiment]}`}>
          <Arrow className="size-3.5" aria-hidden="true" />
          {formatKpiChange(kpi)}
          <span className="sr-only"> ({SENTIMENT_TEXT[kpi.sentiment]})</span>
        </span>
        <span className="tabular text-ink-3">vs {formatKpiValue(kpi, kpi.previous)}</span>
      </div>
    </div>
  );
}
