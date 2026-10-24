import { describe, expect, it } from "vitest";

import { presetRange } from "@/components/shell/FiltersProvider";
import { buildUrl } from "@/lib/api";
import { addDays, formatBucket, formatCurrency, formatKpiChange, formatKpiValue, formatPercent } from "@/lib/format";
import type { FilterOptions, Kpi } from "@/types/api";

const kpi = (over: Partial<Kpi>): Kpi => ({
  key: "net_revenue", label: "Net Revenue", unit: "currency", definition: "", value: 0, previous: 0,
  abs_change: 0, pct_change: 0, direction: "flat", sentiment: "neutral", ...over,
});

describe("formatting", () => {
  it("formats currency and nulls", () => {
    expect(formatCurrency(1234567.89)).toBe("$1,234,568");
    expect(formatCurrency(119.5, true)).toBe("$119.50");
    expect(formatCurrency(null)).toBe("—");
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(34.615)).toBe("34.6%");
  });

  it("formats KPI values by unit", () => {
    expect(formatKpiValue({ unit: "currency", key: "avg_order_value" }, 26)).toBe("$26.00");
    expect(formatKpiValue({ unit: "count", key: "orders" }, 2735)).toBe("2,735");
    expect(formatKpiValue({ unit: "percent", key: "gross_margin_pct" }, null)).toBe("—");
  });

  it("reports percent KPIs in percentage points and missing baselines as n/a", () => {
    expect(formatKpiChange(kpi({ pct_change: 12.33 }))).toBe("+12.3%");
    expect(formatKpiChange(kpi({ pct_change: -4 }))).toBe("-4.0%");
    expect(formatKpiChange(kpi({ pct_change: null }))).toBe("n/a");
    expect(formatKpiChange(kpi({ unit: "percent", abs_change: 0.5, pct_change: null }))).toBe("+0.5 pp");
    expect(formatKpiChange(kpi({ unit: "percent", abs_change: -0.04, pct_change: null }))).toBe("0.0 pp");
  });

  it("formats calendar dates without timezone drift", () => {
    expect(formatBucket("2026-01-01", "month")).toBe("Jan 2026");
    expect(formatBucket("2026-03-30", "week")).toBe("Mar 30");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("api urls", () => {
  it("drops empty params and repeats arrays", () => {
    const url = buildUrl("/dashboard/overview", { start_date: "2026-01-01", store: "", channel: ["online", "marketplace"] });
    expect(url).toMatch(/\/api\/v1\/dashboard\/overview\?start_date=2026-01-01&channel=online&channel=marketplace$/);
  });
});

describe("date presets", () => {
  const options: FilterOptions = { has_data: true, date_min: "2026-05-01", date_max: "2026-06-30", stores: [], categories: [], channels: [] };
  it("anchors to the latest data date and clamps to the earliest", () => {
    expect(presetRange("30d", options)).toEqual({ start: "2026-06-01", end: "2026-06-30" });
    expect(presetRange("90d", options)).toEqual({ start: "2026-05-01", end: "2026-06-30" });
    expect(presetRange("all", options)).toEqual({ start: "2026-05-01", end: "2026-06-30" });
    expect(presetRange("30d", { ...options, date_min: null, date_max: null })).toBeNull();
  });
});
