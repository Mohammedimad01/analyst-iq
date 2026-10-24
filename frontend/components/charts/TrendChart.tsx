"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";

import { EmptyChart } from "@/components/ui/States";
import { formatBucket } from "@/lib/format";
import type { Grain, TrendPoint } from "@/types/api";

export interface Series {
  key: "net_revenue" | "gross_profit" | "orders" | "units";
  label: string;
  color: string;
}

const AXIS = { stroke: "var(--color-axis)", fontSize: 11, tickLine: false } as const;

function TrendTooltip({
  active,
  payload,
  grain,
  series,
  format,
}: Partial<TooltipContentProps> & { grain: Grain; series: Series[]; format: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as TrendPoint;
  const prefix = grain === "week" ? "Week of " : "";
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink">
        {prefix}
        {formatBucket(point.period_start, grain)}
        {point.partial && <span className="ml-1 font-normal text-ink-3">(partial period)</span>}
      </p>
      {series.map((s) => (
        <p key={s.key} className="flex items-center justify-between gap-4 text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-2 rounded-full" style={{ background: s.color }} />
            {s.label}
          </span>
          <span className="tabular font-medium text-ink">{format(point[s.key])}</span>
        </p>
      ))}
    </div>
  );
}

function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  return (
    <div className="mb-2 flex gap-4 text-xs text-ink-2">
      {series.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

export function TrendChart({
  points,
  grain,
  series,
  format,
  axisFormat,
  kind = "line",
  height = 260,
}: {
  points: TrendPoint[];
  grain: Grain;
  series: Series[];
  format: (v: number) => string;
  axisFormat: (v: number) => string;
  kind?: "line" | "bar";
  height?: number;
}) {
  if (!points.length || points.every((p) => series.every((s) => p[s.key] === 0))) {
    return <EmptyChart message="No completed sales in this period." />;
  }
  const Chart = kind === "line" ? LineChart : BarChart;
  return (
    <div>
      <Legend series={series} />
      <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(" and ")} by ${grain}`}>
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={points} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--color-grid)" />
            <XAxis
              dataKey="period_start"
              {...AXIS}
              axisLine={{ stroke: "var(--color-grid)" }}
              tickFormatter={(v: string) => formatBucket(v, grain)}
              minTickGap={24}
            />
            <YAxis {...AXIS} axisLine={false} width={56} tickFormatter={axisFormat} />
            <Tooltip
              cursor={kind === "line" ? { stroke: "var(--color-axis)", strokeWidth: 1 } : { fill: "var(--color-subtle)" }}
              content={(props) => <TrendTooltip {...props} grain={grain} series={series} format={format} />}
            />
            {series.map((s) =>
              kind === "line" ? (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={(d: { cx?: number; cy?: number; index?: number; payload?: TrendPoint }) =>
                    d.payload?.partial ? (
                      <circle key={d.index} cx={d.cx} cy={d.cy} r={3.5} fill="#fff" stroke={s.color} strokeWidth={2} />
                    ) : (
                      <g key={d.index} />
                    )
                  }
                  activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
                  isAnimationActive={false}
                />
              ) : (
                <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false}>
                  {points.map((p) => (
                    <Cell key={p.period_start} fillOpacity={p.partial ? 0.4 : 1} />
                  ))}
                </Bar>
              ),
            )}
          </Chart>
        </ResponsiveContainer>
      </div>
      {points.some((p) => p.partial) && (
        <p className="mt-2 text-xs text-ink-3">
          {kind === "line" ? "Hollow points" : "Lighter bars"} mark partial {grain}s at the edges of the selected range;
          they cover fewer days, so a dip there is not a decline.
        </p>
      )}
    </div>
  );
}
