"""The one implementation of every KPI. Definitions: docs/KPI_DEFINITIONS.md.

All money is aggregated in the database and rounded to cents here with Decimal. Ratios use None for a zero
denominator. Every function takes the same Filters object so KPIs, trends and breakdowns always agree.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import Date, Select, case, cast, distinct, func, literal_column, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product, Store

Grain = Literal["day", "week", "month"]
Dimension = Literal["product", "category", "store", "channel"]
CENT = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class Filters:
    start_date: date
    end_date: date
    stores: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = field(default_factory=tuple)
    channels: tuple[str, ...] = field(default_factory=tuple)

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def previous_period(self) -> "Filters":
        end = self.start_date - timedelta(days=1)
        return Filters(end - timedelta(days=self.days - 1), end, self.stores, self.categories, self.channels)


# ---------------------------------------------------------------- KPI catalogue

@dataclass(frozen=True)
class KpiDef:
    key: str
    label: str
    unit: Literal["currency", "percent", "count"]
    good: Literal["up", "down", "neutral"]
    definition: str


KPI_DEFS: tuple[KpiDef, ...] = (
    KpiDef("net_revenue", "Net Revenue", "currency", "up",
           "Σ(quantity × unit price − discount) over completed orders. Excludes cancelled and returned orders, "
           "tax and shipping."),
    KpiDef("gross_profit", "Gross Profit", "currency", "up",
           "Net Revenue − Σ(quantity × unit cost) over completed orders."),
    KpiDef("gross_margin_pct", "Gross Margin", "percent", "up", "Gross Profit ÷ Net Revenue × 100."),
    KpiDef("orders", "Orders", "count", "up", "Number of distinct completed orders."),
    KpiDef("avg_order_value", "Avg Order Value", "currency", "up", "Net Revenue ÷ completed orders."),
    KpiDef("units_sold", "Units Sold", "count", "up", "Σ quantity over completed orders."),
    KpiDef("gross_sales", "Gross Sales", "currency", "up", "Σ(quantity × unit price) over completed orders."),
    KpiDef("discounts", "Discounts", "currency", "neutral", "Σ discount amount over completed orders."),
    KpiDef("discount_rate_pct", "Discount Rate", "percent", "down", "Discounts ÷ Gross Sales × 100."),
    KpiDef("return_rate_pct", "Return Rate", "percent", "down",
           "Returned orders ÷ (completed + returned orders) × 100."),
    KpiDef("cancellation_rate_pct", "Cancellation Rate", "percent", "down", "Cancelled orders ÷ all orders × 100."),
)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def ratio_pct(numerator, denominator) -> Decimal | None:
    if not denominator:
        return None
    return (Decimal(str(numerator)) / Decimal(str(denominator)) * 100).quantize(CENT, rounding=ROUND_HALF_UP)


def safe_div(numerator, denominator) -> Decimal | None:
    if not denominator:
        return None
    return (Decimal(str(numerator)) / Decimal(str(denominator))).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- shared query pieces

_gross = OrderItem.quantity * OrderItem.unit_price
_cogs = OrderItem.quantity * OrderItem.unit_cost
_completed = Order.status == "completed"


def _filtered(stmt: Select, org_id: int, f: Filters) -> Select:
    """Apply the same joins and filters to any line-level aggregate query."""
    stmt = (stmt.select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .join(Store, Store.id == Order.store_id)
            .where(Order.organization_id == org_id, Order.order_date.between(f.start_date, f.end_date)))
    if f.stores:
        stmt = stmt.where(Store.store_code.in_(f.stores))
    if f.categories:
        stmt = stmt.where(Product.category.in_(f.categories))
    if f.channels:
        stmt = stmt.where(Order.channel.in_(f.channels))
    return stmt


def _when_completed(expr):
    return case((_completed, expr), else_=None)


# ---------------------------------------------------------------- summary KPIs

def summary(db: Session, org_id: int, f: Filters) -> dict[str, Decimal | int | None]:
    stmt = _filtered(select(
        func.sum(_when_completed(_gross)),
        func.sum(_when_completed(OrderItem.discount_amount)),
        func.sum(_when_completed(_cogs)),
        func.sum(_when_completed(OrderItem.quantity)),
        func.count(distinct(_when_completed(Order.id))),
        func.count(distinct(case((Order.status == "returned", Order.id), else_=None))),
        func.count(distinct(case((Order.status == "cancelled", Order.id), else_=None))),
        func.count(distinct(Order.id)),
    ), org_id, f)
    gross, discounts, cogs, units, completed, returned, cancelled, all_orders = db.execute(stmt).one()

    gross_sales, discounts, cogs = money(gross), money(discounts), money(cogs)
    net = gross_sales - discounts
    profit = net - cogs
    return {
        "net_revenue": net,
        "gross_profit": profit,
        "gross_margin_pct": ratio_pct(profit, net),
        "orders": completed,
        "avg_order_value": safe_div(net, completed),
        "units_sold": int(units or 0),
        "gross_sales": gross_sales,
        "discounts": discounts,
        "discount_rate_pct": ratio_pct(discounts, gross_sales),
        "return_rate_pct": ratio_pct(returned, completed + returned),
        "cancellation_rate_pct": ratio_pct(cancelled, all_orders),
    }


def compare(kpi: KpiDef, current, previous) -> dict:
    """Change vs comparison period. Percent KPIs change in percentage points, so pct_change is None."""
    abs_change = None if current is None or previous is None else current - previous
    pct_change = None
    if kpi.unit != "percent" and abs_change is not None and previous:
        pct_change = ratio_pct(abs_change, abs(previous))
    if abs_change is None or abs_change == 0:
        direction = "flat"
    else:
        direction = "up" if abs_change > 0 else "down"
    if direction == "flat" or kpi.good == "neutral":
        sentiment = "neutral"
    else:
        sentiment = "positive" if direction == kpi.good else "negative"
    return {"key": kpi.key, "label": kpi.label, "unit": kpi.unit, "definition": kpi.definition,
            "value": current, "previous": previous, "abs_change": abs_change, "pct_change": pct_change,
            "direction": direction, "sentiment": sentiment}


def kpis_with_comparison(db: Session, org_id: int, f: Filters) -> list[dict]:
    current = summary(db, org_id, f)
    previous = summary(db, org_id, f.previous_period())
    return [compare(k, current[k.key], previous[k.key]) for k in KPI_DEFS]


# ---------------------------------------------------------------- trends

def auto_grain(f: Filters) -> Grain:
    if f.days <= 45:
        return "day"
    return "week" if f.days <= 210 else "month"


def bucket_start(d: date, grain: Grain) -> date:
    if grain == "week":
        return d - timedelta(days=d.weekday())
    if grain == "month":
        return d.replace(day=1)
    return d


def _next_bucket(d: date, grain: Grain) -> date:
    if grain == "week":
        return d + timedelta(days=7)
    if grain == "month":
        return (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return d + timedelta(days=1)


def _bucket_expr(dialect: str, grain: Grain):
    if grain == "day":
        return Order.order_date
    # Constants are inlined, not bound: PostgreSQL only matches SELECT and GROUP BY expressions when they are
    # textually identical, and two bound parameters are not. `grain` is a validated Literal, never user text.
    if dialect == "postgresql":
        return cast(func.date_trunc(literal_column(f"'{grain}'"), Order.order_date), Date)
    # SQLite: Monday on/before the date, or first of month.
    modifiers = ("'-6 days'", "'weekday 1'") if grain == "week" else ("'start of month'",)
    return func.date(Order.order_date, *(literal_column(m) for m in modifiers), type_=Date)


def trend(db: Session, org_id: int, f: Filters, grain: Grain | None = None) -> dict:
    grain = grain or auto_grain(f)
    bucket = _bucket_expr(db.get_bind().dialect.name, grain).label("bucket")
    stmt = _filtered(select(
        bucket,
        func.sum(_gross - OrderItem.discount_amount),
        func.sum(_gross - OrderItem.discount_amount - _cogs),
        func.count(distinct(Order.id)),
        func.sum(OrderItem.quantity),
    ), org_id, f).where(_completed).group_by(bucket)
    rows = {r[0]: r[1:] for r in db.execute(stmt).all()}

    points = []
    current = bucket_start(f.start_date, grain)
    while current <= f.end_date:
        net, profit, orders, units = rows.get(current, (0, 0, 0, 0))
        next_start = _next_bucket(current, grain)
        points.append({"period_start": current, "net_revenue": money(net), "gross_profit": money(profit),
                       "orders": int(orders or 0), "units": int(units or 0),
                       "partial": current < f.start_date or next_start - timedelta(days=1) > f.end_date})
        current = next_start
    return {"grain": grain, "points": points}


# ---------------------------------------------------------------- breakdowns

_DIMENSIONS = {
    "product": (Product.sku, Product.name),
    "category": (Product.category, Product.category),
    "store": (Store.store_code, Store.name),
    "channel": (Order.channel, Order.channel),
}
SORT_KEYS = ("net_revenue", "gross_profit", "gross_margin_pct", "units", "orders")


def breakdown(db: Session, org_id: int, f: Filters, dimension: Dimension) -> list[dict]:
    """All groups for the dimension, sorted by net revenue (desc)."""
    key_col, label_col = _DIMENSIONS[dimension]
    stmt = _filtered(select(
        key_col, label_col,
        func.sum(_gross - OrderItem.discount_amount),
        func.sum(_cogs),
        func.sum(OrderItem.quantity),
        func.count(distinct(Order.id)),
    ), org_id, f).where(_completed).group_by(key_col, label_col)

    rows = []
    for key, label, net, cogs, units, orders in db.execute(stmt).all():
        net, cogs = money(net), money(cogs)
        rows.append({"key": key, "label": label, "net_revenue": net, "gross_profit": net - cogs,
                     "gross_margin_pct": ratio_pct(net - cogs, net), "units": int(units or 0),
                     "orders": int(orders or 0)})
    total = sum((r["net_revenue"] for r in rows), ZERO)
    for r in rows:
        r["share_pct"] = ratio_pct(r["net_revenue"], total)
    rows.sort(key=lambda r: (-r["net_revenue"], str(r["key"])))
    return rows


def sort_rows(rows: list[dict], sort: str, descending: bool) -> list[dict]:
    """Sort with None (undefined ratios) always last."""
    present = [r for r in rows if r[sort] is not None]
    missing = [r for r in rows if r[sort] is None]
    present.sort(key=lambda r: (r[sort], str(r["key"])), reverse=descending)
    return present + missing


# ---------------------------------------------------------------- filter options

def filter_options(db: Session, org_id: int) -> dict:
    date_min, date_max = db.execute(select(func.min(Order.order_date), func.max(Order.order_date))
                                    .where(Order.organization_id == org_id)).one()
    stores = db.execute(select(Store.store_code, Store.name).where(Store.organization_id == org_id)
                        .order_by(Store.name)).all()
    categories = db.scalars(select(Product.category).distinct().where(Product.organization_id == org_id)
                            .order_by(Product.category)).all()
    channels = db.scalars(select(Order.channel).distinct().where(Order.organization_id == org_id)
                          .order_by(Order.channel)).all()
    return {"has_data": date_min is not None, "date_min": date_min, "date_max": date_max,
            "stores": [{"code": c, "name": n} for c, n in stores], "categories": list(categories),
            "channels": list(channels)}



def change_drivers(db: Session, org_id: int, f: Filters, dimension: Dimension) -> list[dict]:
    """Net revenue per group in the current vs the previous equal-length period, with each group's share of the
    total change. Sorted by absolute change (largest movers first)."""
    current = {r["key"]: r for r in breakdown(db, org_id, f, dimension)}
    previous = {r["key"]: r for r in breakdown(db, org_id, f.previous_period(), dimension)}
    total_change = sum((r["net_revenue"] for r in current.values()), ZERO) - \
        sum((r["net_revenue"] for r in previous.values()), ZERO)
    rows = []
    for key in current.keys() | previous.keys():
        cur, prev = current.get(key), previous.get(key)
        now = cur["net_revenue"] if cur else money(0)
        before = prev["net_revenue"] if prev else money(0)
        rows.append({"key": key, "label": (cur or prev)["label"], "net_revenue": now, "previous_net_revenue": before,
                     "change": now - before, "change_pct": ratio_pct(now - before, before),
                     "share_of_total_change_pct": ratio_pct(now - before, abs(total_change)) if total_change else None,
                     "gross_margin_pct": cur["gross_margin_pct"] if cur else None,
                     "previous_gross_margin_pct": prev["gross_margin_pct"] if prev else None})
    rows.sort(key=lambda r: (-abs(r["change"]), str(r["key"])))
    return rows
