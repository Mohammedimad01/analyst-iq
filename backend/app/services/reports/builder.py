"""Report content, built only from the KPI engine and the anomaly detector (the same code the dashboard uses).

A report is a title, metadata, notes and a list of tables. Renderers (render.py) turn it into PDF or CSV.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.analytics import metrics
from app.services.analytics.metrics import KPI_DEFS, Filters
from app.services.anomaly_detection.detector import CHANNEL_LABELS, DetectionConfig, detect

Kind = str  # text | currency | percent | count | number | date


@dataclass
class Table:
    title: str
    columns: list[tuple[str, Kind]]
    rows: list[list]
    note: str | None = None


@dataclass
class Report:
    title: str
    meta: list[tuple[str, str]]
    notes: list[str]
    tables: list[Table] = field(default_factory=list)


REPORT_TITLES = {
    "executive": "Executive Summary",
    "sales": "Sales Performance",
    "product": "Product Performance",
    "store": "Store & Channel Performance",
    "customer": "Customer Analytics",
    "profitability": "Profitability",
}
SYNTHETIC_NOTE = ("SYNTHETIC DEMO DATA: this report is generated from a synthetic dataset. "
                  "It does not describe the performance of a real business.")
LIMITATIONS = (
    "Revenue counts completed orders only; cancelled and returned orders are excluded. Taxes and shipping are not "
    "included.",
    "Anomalies are statistical deviations from each segment's own baseline, not confirmed business problems.",
    "The data contains no marketing, traffic, inventory or cost-to-serve information, so causes cannot be "
    "established from it.",
)


# ---------------------------------------------------------------- sections

def kpi_table(db: Session, org_id: int, f: Filters, keys: tuple[str, ...] | None = None) -> Table:
    kpis = [k for k in metrics.kpis_with_comparison(db, org_id, f) if keys is None or k["key"] in keys]
    rows = []
    for k in kpis:
        unit = "percent" if k["unit"] == "percent" else k["unit"]
        change = (k["abs_change"], "pp") if k["unit"] == "percent" else (k["pct_change"], "percent")
        rows.append([k["label"], (k["value"], unit), (k["previous"], unit), change])
    return Table("Key metrics", [("Metric", "text"), ("Selected period", "mixed"), ("Comparison period", "mixed"),
                                 ("Change", "mixed")], rows)


def trend_table(db: Session, org_id: int, f: Filters) -> Table:
    t = metrics.trend(db, org_id, f)
    rows = [[p["period_start"], p["net_revenue"], p["gross_profit"], p["orders"], p["units"],
             "partial" if p["partial"] else ""] for p in t["points"]]
    return Table(f"Trend by {t['grain']}", [("Period start", "date"), ("Net revenue", "currency"),
                                            ("Gross profit", "currency"), ("Orders", "count"), ("Units", "count"),
                                            ("Note", "text")], rows,
                 note="Partial periods at the edges cover fewer days; a dip there is not a decline.")


def breakdown_table(db: Session, org_id: int, f: Filters, dimension: str, title: str, sort: str = "net_revenue",
                    descending: bool = True, limit: int | None = None, show_key: bool = False) -> Table:
    rows = metrics.sort_rows(metrics.breakdown(db, org_id, f, dimension), sort, descending)
    total = len(rows)
    rows = rows[:limit] if limit else rows
    label = (lambda r: CHANNEL_LABELS.get(r["key"], r["key"])) if dimension == "channel" else (lambda r: r["label"])
    columns = [(dimension.capitalize(), "text")] + ([("Code", "text")] if show_key else []) + [
        ("Net revenue", "currency"), ("Gross profit", "currency"), ("Margin", "percent"), ("Units", "count"),
        ("Orders", "count"), ("Share", "percent")]
    out = [[label(r)] + ([r["key"]] if show_key else []) + [r["net_revenue"], r["gross_profit"],
                                                           r["gross_margin_pct"], r["units"], r["orders"],
                                                           r["share_pct"]] for r in rows]
    note = f"Showing {len(out)} of {total}." if limit and total > len(out) else None
    return Table(title, columns, out, note)


def anomaly_table(db: Session, org_id: int, f: Filters) -> Table:
    found = detect(db, org_id, DetectionConfig(), f.start_date, f.end_date)["anomalies"]
    found = [a for a in found if a["severity"] in ("high", "medium")]
    rows = [[a["severity"], f"{a['dimension']}: {a['segment_label']}", a["metric_label"],
             date.fromisoformat(a["period_start"]), a["observed"], a["expected"],
             # Rate metrics change in percentage points; a % change of a % would mislead.
             (a["abs_diff"], "pp") if a["metric"].endswith("_pct") else (a["pct_diff"], "percent")] for a in found]
    return Table("Detected anomalies (high and medium)", [
        ("Severity", "text"), ("Segment", "text"), ("Metric", "text"), ("Period start", "date"),
        ("Observed", "number"), ("Expected", "number"), ("Difference", "mixed")], rows,
        note="Detection uses complete periods only and ignores store/category/channel filters. "
             "Statistical deviations, not confirmed problems." if rows else "No high or medium anomalies.")


def customer_tables(db: Session, org_id: int, f: Filters) -> list[Table]:
    c = metrics.customer_analytics(db, org_id, f)
    kpi_rows = []
    for k in c["kpis"]:
        unit = "percent" if k["unit"] == "percent" else ("number" if k["key"] == "orders_per_customer" else k["unit"])
        change = (k["abs_change"], "pp") if k["unit"] == "percent" else (k["pct_change"], "percent")
        kpi_rows.append([k["label"], (k["value"], unit), (k["previous"], unit), change])
    conc = c["concentration"]
    return [
        Table("Customer metrics", [("Metric", "text"), ("Selected period", "mixed"), ("Comparison period", "mixed"),
                                   ("Change", "mixed")], kpi_rows,
              note=" ".join(c["warnings"]) or None),
        Table("Customer segments", [("Segment", "text"), ("Customers", "count"), ("Orders", "count"),
                                    ("Net revenue", "currency"), ("Share", "percent")],
              [[s["segment"], s["customers"], s["orders"], s["net_revenue"], s["share_pct"]] for s in c["segments"]]),
        Table("Top customers", [("Customer code", "text"), ("Orders", "count"), ("Net revenue", "currency"),
                                ("Share of identified revenue", "percent")],
              [[t["customer_code"], t["orders"], t["net_revenue"], t["share_pct"]] for t in c["top_customers"]],
              note=f"Top {conc['top_fraction_pct']}% of customers ({conc['top_count']} of {conc['item_count']}) "
                   f"account for {conc['share_pct']}% of identified revenue." if conc["share_pct"] is not None
              else None),
    ]


def definitions_table() -> Table:
    return Table("Metric definitions", [("Metric", "text"), ("Definition", "text")],
                 [[k.label, k.definition] for k in KPI_DEFS])


# ---------------------------------------------------------------- reports

def has_sales(db: Session, org_id: int, f: Filters) -> bool:
    return (metrics.summary(db, org_id, f)["orders"] or 0) > 0


def build_report(db: Session, org_id: int, report_type: str, f: Filters, organization: str,
                 synthetic: bool) -> Report:
    prev = f.previous_period()
    filters = "; ".join(f"{n}: {', '.join(v)}" for n, v in (("store", f.stores), ("category", f.categories),
                                                             ("channel", f.channels)) if v) or "none"
    report = Report(
        title=f"{REPORT_TITLES[report_type]} - {organization}",
        meta=[("Period", f"{f.start_date.isoformat()} to {f.end_date.isoformat()} ({f.days} days)"),
              ("Compared with", f"{prev.start_date.isoformat()} to {prev.end_date.isoformat()}"),
              ("Filters", filters)],
        notes=([SYNTHETIC_NOTE] if synthetic else []) + list(LIMITATIONS),
    )
    t = report.tables
    if report_type == "executive":
        t += [kpi_table(db, org_id, f), trend_table(db, org_id, f),
              breakdown_table(db, org_id, f, "category", "Revenue by category"),
              breakdown_table(db, org_id, f, "store", "Revenue by store"),
              breakdown_table(db, org_id, f, "channel", "Revenue by channel"),
              anomaly_table(db, org_id, f)]
    elif report_type == "sales":
        t += [kpi_table(db, org_id, f), trend_table(db, org_id, f),
              breakdown_table(db, org_id, f, "category", "By category"),
              breakdown_table(db, org_id, f, "channel", "By channel")]
    elif report_type == "product":
        t += [kpi_table(db, org_id, f, ("net_revenue", "gross_profit", "gross_margin_pct", "units_sold")),
              breakdown_table(db, org_id, f, "product", "All products by net revenue", show_key=True)]
    elif report_type == "store":
        t += [breakdown_table(db, org_id, f, "store", "Stores", show_key=True),
              breakdown_table(db, org_id, f, "channel", "Sales channels")]
    elif report_type == "customer":
        t += customer_tables(db, org_id, f)
    elif report_type == "profitability":
        t += [kpi_table(db, org_id, f, ("net_revenue", "gross_profit", "gross_margin_pct", "discounts",
                                        "discount_rate_pct")),
              breakdown_table(db, org_id, f, "category", "Categories by margin (lowest first)", "gross_margin_pct",
                              descending=False),
              breakdown_table(db, org_id, f, "product", "Lowest-margin products", "gross_margin_pct",
                              descending=False, limit=15, show_key=True)]
    t.append(definitions_table())
    return report


def cell_value(value) -> object:
    """Unwrap (value, kind) pairs used by mixed-unit columns."""
    return value[0] if isinstance(value, tuple) else value


def as_number(value) -> float | None:
    v = cell_value(value)
    return float(v) if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) else None
