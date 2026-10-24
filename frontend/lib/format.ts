import type { Kpi } from "@/types/api";

// shortcut: currency is fixed to USD for the synthetic demo dataset; make it an org setting with real tenants.
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const currencyCents = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const compactCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const DASH = "—";

export function formatCurrency(value: number | null, cents = false): string {
  if (value === null) return DASH;
  return (cents ? currencyCents : currency).format(value);
}

export function formatCompactCurrency(value: number): string {
  return compactCurrency.format(value);
}

export function formatNumber(value: number | null): string {
  return value === null ? DASH : integer.format(value);
}

export function formatPercent(value: number | null, digits = 1): string {
  return value === null ? DASH : `${value.toFixed(digits)}%`;
}

export function formatKpiValue(kpi: Pick<Kpi, "unit" | "key">, value: number | null): string {
  if (kpi.unit === "currency") return formatCurrency(value, kpi.key === "avg_order_value");
  if (kpi.unit === "percent") return formatPercent(value);
  return formatNumber(value);
}

/** Signed to one decimal, without a "-0.0" when a small change rounds away. */
function signed(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "0.0";
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}

/** "+12.3%" for amounts; "+0.8 pp" for KPIs that are already percentages. */
export function formatKpiChange(kpi: Kpi): string {
  if (kpi.unit === "percent") return kpi.abs_change === null ? DASH : `${signed(kpi.abs_change)} pp`;
  return kpi.pct_change === null ? "n/a" : `${signed(kpi.pct_change)}%`;
}

const CHANNEL_LABELS: Record<string, string> = { in_store: "In-store", online: "Online", marketplace: "Marketplace" };
export const channelLabel = (key: string) => CHANNEL_LABELS[key] ?? key;

const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const monthYear = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
const longDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

// API dates are calendar dates (YYYY-MM-DD); format in UTC so the viewer's timezone never shifts the day.
const asDate = (iso: string) => new Date(`${iso}T00:00:00Z`);
export const formatDate = (iso: string) => longDate.format(asDate(iso));
export const formatBucket = (iso: string, grain: "day" | "week" | "month") =>
  grain === "month" ? monthYear.format(asDate(iso)) : shortDate.format(asDate(iso));

export function addDays(iso: string, days: number): string {
  const d = asDate(iso);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
