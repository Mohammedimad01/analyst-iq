"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";

import { EmptyChart } from "@/components/ui/States";

export interface HBarDatum {
  label: string;
  value: number | null;
  detail?: string;
}

function HBarTooltip({ active, payload, format }: Partial<TooltipContentProps> & { format: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as HBarDatum;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-ink">{d.label}</p>
      <p className="tabular text-ink-2">{d.value === null ? "n/a" : format(d.value)}</p>
      {d.detail && <p className="text-ink-3">{d.detail}</p>}
    </div>
  );
}

/** Ranked horizontal bars, one series, one color (nominal categories never get a value ramp). */
export function HBarChart({
  data,
  format,
  axisFormat,
  labelWidth = 130,
  color = "var(--color-series-1)",
  ariaLabel,
}: {
  data: HBarDatum[];
  format: (v: number) => string;
  axisFormat: (v: number) => string;
  labelWidth?: number;
  color?: string;
  ariaLabel: string;
}) {
  if (!data.length) return <EmptyChart />;
  const height = data.length * 30 + 28;
  return (
    <div style={{ height }} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke="var(--color-grid)" />
          <XAxis type="number" stroke="var(--color-axis)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={axisFormat} />
          <YAxis
            type="category"
            dataKey="label"
            width={labelWidth}
            stroke="var(--color-ink-2)"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: "var(--color-axis)" }}
            interval={0}
          />
          <Tooltip cursor={{ fill: "var(--color-subtle)" }} content={(props) => <HBarTooltip {...props} format={format} />} />
          <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
