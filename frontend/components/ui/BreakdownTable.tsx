import { ArrowDown, ArrowUp } from "lucide-react";

import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { BreakdownRow, SortKey } from "@/types/api";

const COLUMNS: { key: SortKey | "share_pct"; label: string; format: (r: BreakdownRow) => string }[] = [
  { key: "net_revenue", label: "Net revenue", format: (r) => formatCurrency(r.net_revenue) },
  { key: "gross_profit", label: "Gross profit", format: (r) => formatCurrency(r.gross_profit) },
  { key: "gross_margin_pct", label: "Margin", format: (r) => formatPercent(r.gross_margin_pct) },
  { key: "units", label: "Units", format: (r) => formatNumber(r.units) },
  { key: "orders", label: "Orders", format: (r) => formatNumber(r.orders) },
  { key: "share_pct", label: "Share", format: (r) => formatPercent(r.share_pct) },
];

export function BreakdownTable({
  rows,
  labelHeader,
  labelFormat = (r) => r.label,
  showKey = false,
  sort,
  order,
  onSort,
}: {
  rows: BreakdownRow[];
  labelHeader: string;
  labelFormat?: (r: BreakdownRow) => string;
  showKey?: boolean;
  sort?: SortKey;
  order?: "asc" | "desc";
  onSort?: (key: SortKey) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-3">
            <th scope="col" className="py-2 pr-3 font-medium">{labelHeader}</th>
            {COLUMNS.map((c) => {
              const sortable = onSort && c.key !== "share_pct";
              const active = sort === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className="py-2 pl-3 text-right font-medium"
                  aria-sort={active ? (order === "asc" ? "ascending" : "descending") : undefined}
                >
                  {sortable ? (
                    <button
                      onClick={() => onSort(c.key as SortKey)}
                      className={`inline-flex items-center gap-1 uppercase hover:text-ink ${active ? "text-ink" : ""}`}
                    >
                      {c.label}
                      {active && (order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b border-line/70 last:border-0 hover:bg-subtle">
              <th scope="row" className="py-2 pr-3 text-left font-medium text-ink">
                {labelFormat(r)}
                {showKey && <span className="ml-2 text-xs font-normal text-ink-3">{r.key}</span>}
              </th>
              {COLUMNS.map((c) => (
                <td key={c.key} className="tabular py-2 pl-3 text-right text-ink-2">
                  {c.format(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
