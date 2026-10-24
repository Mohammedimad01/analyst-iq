"""Interpretable statistical anomaly detection. Methods and thresholds: docs/INSIGHTS.md.

Every detector compares a segment with a baseline built only from *earlier complete periods*, and most compare it
with the rest of the business so company-wide seasonality (December, Black Friday) cancels out. A flagged item is a
statistical anomaly, not a confirmed business problem.
"""

import math
from datetime import date, timedelta

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product, Store

CHANNEL_LABELS = {"in_store": "In-store", "online": "Online", "marketplace": "Marketplace"}
NOTE = "Statistical anomaly: a deviation from the baseline, not a confirmed business problem."


class DetectionConfig(BaseModel):
    volume_min_pct: float = Field(35.0, ge=5, description="Weekly segment volume: minimum |% difference|")
    volume_min_z: float = Field(4.0, ge=1)
    volume_min_expected: float = Field(15.0, ge=1, description="Minimum expected weekly orders to evaluate")
    volume_baseline_weeks: int = Field(8, ge=3, le=26)
    spike_min_pct: float = Field(75.0, ge=10, description="Daily channel spike: minimum |% difference|")
    spike_min_z: float = Field(4.0, ge=1)
    spike_min_expected: float = Field(5.0, ge=1)
    spike_baseline_weeks: int = Field(8, ge=3, le=26, description="Same-weekday history used for daily spikes")
    discount_min_excess_pp: float = Field(8.0, ge=1, description="Category discount rate vs usual gap, in pp")
    discount_min_weekly_gross: float = Field(1000.0, ge=0)
    discount_baseline_weeks: int = Field(8, ge=3, le=26)
    returns_min_increase_pp: float = Field(10.0, ge=1)
    returns_min_orders: int = Field(20, ge=5)
    returns_min_z: float = Field(3.0, ge=1)
    returns_baseline_months: int = Field(6, ge=2, le=12)
    yoy_min_pct: float = Field(40.0, ge=5, description="Total weekly revenue vs same week last year")


def _severity(pct: float | None, z: float | None, pp: float | None = None) -> str:
    if pp is not None:
        return "high" if pp >= 15 else "medium" if pp >= 10 else "low"
    pct = abs(pct or 0)
    if z is None:  # no significance test (year-over-year): size alone
        return "high" if pct >= 60 else "medium" if pct >= 45 else "low"
    z = abs(z)
    # A big % change on a small count is common, so "high" also needs strong significance.
    if z >= 6 or (pct >= 60 and z >= 4.5):
        return "high"
    return "medium" if pct >= 45 or z >= 4.5 else "low"


def _round(value, digits=2):
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), digits)


def _anomaly(detector, metric, metric_label, dimension, key, label, grain, start: date, end: date, observed, expected,
             z, method, evidence, pp_change: float | None = None) -> dict:
    abs_diff = observed - expected
    pct = abs_diff / expected * 100 if expected else None
    return {
        "key": f"{detector}:{dimension}:{key}:{start.isoformat()}",
        "detector": detector, "metric": metric, "metric_label": metric_label,
        "dimension": dimension, "segment_key": str(key), "segment_label": label,
        "grain": grain, "period_start": start.isoformat(), "period_end": end.isoformat(),
        "observed": _round(observed), "expected": _round(expected), "abs_diff": _round(abs_diff),
        "pct_diff": _round(pct, 1), "z_score": _round(z), "direction": "up" if abs_diff > 0 else "down",
        "severity": _severity(pct, z, abs(pp_change) if pp_change is not None else None),
        "method": method, "evidence": evidence, "note": NOTE,
    }


# ---------------------------------------------------------------- periods

def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def complete_periods(index: pd.Index, grain: str, data_min: date, data_max: date) -> list[date]:
    """Periods entirely inside the data range: partial first/last weeks or months are never judged."""
    out = []
    for p in index:
        end = p if grain == "day" else p + timedelta(days=6) if grain == "week" else _next_month(p) - timedelta(days=1)
        if p >= data_min and end <= data_max:
            out.append(p)
    return out


def _period_end(p: date, grain: str) -> date:
    return p if grain == "day" else p + timedelta(days=6) if grain == "week" else _next_month(p) - timedelta(days=1)


# ---------------------------------------------------------------- detectors (pure, testable)

def segment_vs_rest(counts: pd.DataFrame, labels: dict, dimension: str, grain: str, baseline_n: int,
                    min_pct: float, min_z: float, min_expected: float, evaluate: list[date]) -> list[dict]:
    """counts: index = period start, columns = segment, values = completed orders.

    expected = median(segment ÷ rest-of-business over the previous `baseline_n` periods) × rest-of-business now.
    The z-score includes the noise of the rest-of-business count: Var ≈ e·(1 + ratio). Without that term a dominant
    segment looks anomalous whenever the small remainder happens to dip.
    The segment must also move in the same direction against its own recent median (at least half the threshold),
    so one segment's drop does not make the others look like spikes (the "mirror" effect).
    """
    total = counts.sum(axis=1)
    out = []
    unit = "complete weeks" if grain == "week" else "days"
    for seg in counts.columns:
        obs = counts[seg]
        rest = total - obs
        ratio = obs / rest.where(rest > 0)
        baseline = ratio.shift(1).rolling(baseline_n, min_periods=max(3, baseline_n // 2)).median()
        expected = baseline * rest
        own = obs.shift(1).rolling(baseline_n, min_periods=max(3, baseline_n // 2)).median()
        for p in evaluate:
            exp = expected.get(p)
            if exp is None or pd.isna(exp) or exp < min_expected or pd.isna(own[p]) or own[p] <= 0:
                continue
            o = float(obs[p])
            z = (o - exp) / math.sqrt(exp * (1 + baseline[p]))
            pct = (o - exp) / exp * 100
            own_pct = (o - own[p]) / own[p] * 100
            if abs(pct) >= min_pct and abs(z) >= min_z and pct * own_pct > 0 and abs(own_pct) >= min_pct / 2:
                window_start = counts.index[max(0, counts.index.get_loc(p) - baseline_n)]
                out.append(_anomaly(
                    f"segment_volume_{grain}", "orders", "Completed orders", dimension, seg, labels.get(seg, seg),
                    grain, p, _period_end(p, grain), o, float(exp), z,
                    f"Orders relative to the rest of the business, compared with the median ratio over the previous "
                    f"{baseline_n} {unit}; z-score includes noise in both counts. Company-wide seasonality cancels out.",
                    {"rest_of_business_orders": int(rest[p]), "baseline_ratio_to_rest": _round(baseline[p], 4),
                     "own_recent_median": _round(own[p]), "pct_vs_own_recent_median": _round(own_pct, 1),
                     "baseline_window_start": window_start.isoformat(),
                     "baseline_window_end": (p - timedelta(days=1)).isoformat()},
                ))
    return out


def daily_spike(counts: pd.DataFrame, labels: dict, dimension: str, cfg: DetectionConfig,
                evaluate: list[date]) -> list[dict]:
    """counts: index = every day, columns = segment. Flags a day only when two tests agree:
    1. vs the segment's own history: median of the same weekday over the previous weeks (weekday pattern);
    2. vs the rest of the business that day, so company-wide surges (Black Friday) are not flagged.
    """
    total = counts.sum(axis=1)
    n = cfg.spike_baseline_weeks
    out = []
    for seg in counts.columns:
        obs = counts[seg]
        same_weekday = pd.concat([obs.shift(7 * k) for k in range(1, n + 1)], axis=1)
        typical = same_weekday.median(axis=1).where(same_weekday.notna().sum(axis=1) >= max(3, n // 2))
        rest = total - obs
        ratio = obs / rest.where(rest > 0)
        ratio_base = ratio.shift(1).rolling(7 * n // 2, min_periods=14).median()
        for p in evaluate:
            exp, r = typical.get(p), ratio_base.get(p)
            if exp is None or pd.isna(exp) or exp < cfg.spike_min_expected or pd.isna(r):
                continue
            o = float(obs[p])
            pct = (o - exp) / exp * 100
            z = (o - exp) / math.sqrt(exp)
            rel_exp = r * rest[p]
            z_rel = (o - rel_exp) / math.sqrt(max(rel_exp, 1.0) * (1 + r))
            if abs(pct) >= cfg.spike_min_pct and abs(z) >= cfg.spike_min_z and abs(z_rel) >= 3 and z * z_rel > 0:
                out.append(_anomaly(
                    "segment_spike_daily", "orders", "Completed orders", dimension, seg, labels.get(seg, seg), "day",
                    p, p, o, float(exp), z,
                    f"Orders vs the median of the same weekday over the previous {n} weeks (Poisson z-score), "
                    f"confirmed against the rest of the business that day so company-wide surges are excluded.",
                    {"weekday": p.strftime("%A"), "same_weekday_median": _round(exp),
                     "expected_from_rest_of_business": _round(rel_exp), "z_vs_rest_of_business": _round(z_rel),
                     "rest_of_business_orders": int(rest[p])},
                ))
    return out


def category_discount_excess(gross: pd.DataFrame, discount: pd.DataFrame, cfg: DetectionConfig,
                             evaluate: list[date]) -> list[dict]:
    """gross/discount: index = week start, columns = category. Rates in percent."""
    total_gross, total_disc = gross.sum(axis=1), discount.sum(axis=1)
    out = []
    for cat in gross.columns:
        rate = discount[cat] / gross[cat].where(gross[cat] > 0) * 100
        rest_rate = (total_disc - discount[cat]) / (total_gross - gross[cat]).where(lambda s: s > 0) * 100
        excess = rate - rest_rate
        n = cfg.discount_baseline_weeks
        baseline_excess = excess.shift(1).rolling(n, min_periods=max(3, n // 2)).median()
        for p in evaluate:
            if gross[cat][p] < cfg.discount_min_weekly_gross or pd.isna(baseline_excess.get(p)) or pd.isna(rate[p]):
                continue
            expected_rate = rest_rate[p] + baseline_excess[p]
            delta = rate[p] - expected_rate
            if delta >= cfg.discount_min_excess_pp:
                out.append(_anomaly(
                    "category_discount_weekly", "discount_rate_pct", "Discount rate (%)", "category", cat, cat, "week",
                    p, _period_end(p, "week"), float(rate[p]), float(expected_rate), None,
                    f"Category discount rate minus the rest of the business, compared with its median gap over the "
                    f"previous {n} complete weeks. Change is in percentage points.",
                    {"gross_sales": _round(gross[cat][p]), "discounts": _round(discount[cat][p]),
                     "rest_of_business_discount_rate_pct": _round(rest_rate[p]),
                     "usual_gap_pp": _round(baseline_excess[p]), "change_pp": _round(delta)},
                    pp_change=float(delta),
                ))
    return out


def product_return_spike(completed: pd.DataFrame, returned: pd.DataFrame, labels: dict, cfg: DetectionConfig,
                         evaluate: list[date]) -> list[dict]:
    """completed/returned: index = month start, columns = sku, values = orders containing the product."""
    out = []
    n = cfg.returns_baseline_months
    for sku in completed.columns.union(returned.columns):
        c = completed.get(sku, pd.Series(0, index=completed.index)).reindex(completed.index, fill_value=0)
        r = returned.get(sku, pd.Series(0, index=completed.index)).reindex(completed.index, fill_value=0)
        orders = c + r
        base_r = r.shift(1).rolling(n, min_periods=max(2, n // 2)).sum()
        base_n = orders.shift(1).rolling(n, min_periods=max(2, n // 2)).sum()
        for p in evaluate:
            if orders[p] < cfg.returns_min_orders or pd.isna(base_n.get(p)) or base_n[p] < 30:
                continue
            rate, p0 = r[p] / orders[p], base_r[p] / base_n[p]
            p0_safe = min(max(p0, 0.01), 0.99)
            z = (rate - p0) / math.sqrt(p0_safe * (1 - p0_safe) / orders[p])
            delta_pp = (rate - p0) * 100
            if delta_pp >= cfg.returns_min_increase_pp and z >= cfg.returns_min_z:
                out.append(_anomaly(
                    "product_returns_monthly", "return_rate_pct", "Return rate (%)", "product", sku,
                    labels.get(sku, sku), "month", p, _period_end(p, "month"), rate * 100, p0 * 100, z,
                    f"Share of orders containing the product that were returned, compared with the pooled rate of "
                    f"the previous {n} complete months; binomial z-score. Change is in percentage points.",
                    {"orders_with_product": int(orders[p]), "returned_orders": int(r[p]),
                     "baseline_orders": int(base_n[p]), "baseline_returned_orders": int(base_r[p])},
                    pp_change=delta_pp,
                ))
    return out


def total_revenue_yoy(weekly_revenue: pd.Series, cfg: DetectionConfig, evaluate: list[date],
                      data_min: date) -> list[dict]:
    out = []
    for p in evaluate:
        prior = p - timedelta(days=364)  # same ISO weekday, 52 weeks earlier
        # The comparison week must be complete too, or a partial first week looks like a huge jump.
        if prior < data_min or prior not in weekly_revenue.index or weekly_revenue[prior] <= 0:
            continue
        obs, base = float(weekly_revenue[p]), float(weekly_revenue[prior])
        pct = (obs - base) / base * 100
        if abs(pct) >= cfg.yoy_min_pct:
            out.append(_anomaly(
                "total_revenue_yoy", "net_revenue", "Net revenue", "total", "all", "Whole business", "week",
                p, _period_end(p, "week"), obs, base, None,
                "Weekly net revenue compared with the same week one year earlier (52 weeks).",
                {"comparison_week_start": prior.isoformat()},
            ))
    return out


# ---------------------------------------------------------------- data access + orchestration

def _frame(rows, columns) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
    return df


def _pivot(df: pd.DataFrame, period: str, column: str, value: str, full_index: list[date]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=full_index)
    p = df.pivot_table(index=period, columns=column, values=value, aggfunc="sum", fill_value=0)
    return p.reindex(full_index, fill_value=0).astype(float)


def _range(start: date, end: date, grain: str) -> list[date]:
    step = {"day": lambda d: d + timedelta(days=1), "week": lambda d: d + timedelta(days=7), "month": _next_month}[grain]
    first = {"day": start, "week": week_start(start), "month": month_start(start)}[grain]
    out = []
    while first <= end:
        out.append(first)
        first = step(first)
    return out


def detect(db: Session, org_id: int, cfg: DetectionConfig, start: date | None = None,
           end: date | None = None) -> dict:
    data_min, data_max = db.execute(select(func.min(Order.order_date), func.max(Order.order_date))
                                    .where(Order.organization_id == org_id)).one()
    if data_min is None:
        return {"data_range": None, "evaluated_range": None, "anomalies": [], "counts": {}}
    eval_start, eval_end = max(start or data_min, data_min), min(end or data_max, data_max)

    org = Order.organization_id == org_id
    net = OrderItem.quantity * OrderItem.unit_price - OrderItem.discount_amount
    completed = Order.status == "completed"

    # Order counts by day × store × channel (an order belongs to exactly one store and channel).
    orders = _frame(db.execute(
        select(Order.order_date, Store.store_code, Order.channel, func.count(Order.id))
        .join(Store, Store.id == Order.store_id).where(org, completed)
        .group_by(Order.order_date, Store.store_code, Order.channel)).all(),
        ["order_date", "store", "channel", "orders"])
    revenue = _frame(db.execute(
        select(Order.order_date, func.sum(net)).join(OrderItem, OrderItem.order_id == Order.id)
        .where(org, completed).group_by(Order.order_date)).all(), ["order_date", "net_revenue"])
    cat = _frame(db.execute(
        select(Order.order_date, Product.category, func.sum(OrderItem.quantity * OrderItem.unit_price),
               func.sum(OrderItem.discount_amount))
        .join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id)
        .where(org, completed).group_by(Order.order_date, Product.category)).all(),
        ["order_date", "category", "gross", "discount"])
    prod = _frame(db.execute(
        select(Order.order_date, Product.sku, Order.status, func.count(distinct(Order.id)))
        .join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id)
        .where(org, Order.status.in_(("completed", "returned")))
        .group_by(Order.order_date, Product.sku, Order.status)).all(),
        ["order_date", "sku", "status", "orders"])
    store_labels = dict(db.execute(select(Store.store_code, Store.name).where(Store.organization_id == org_id)).all())
    product_labels = dict(db.execute(select(Product.sku, Product.name).where(Product.organization_id == org_id)).all())

    days, weeks, months = (_range(data_min, data_max, g) for g in ("day", "week", "month"))
    in_window = lambda periods, grain: [p for p in complete_periods(pd.Index(periods), grain, data_min, data_max)  # noqa: E731
                                        if p >= eval_start and _period_end(p, grain) <= eval_end]
    eval_days, eval_weeks, eval_months = in_window(days, "day"), in_window(weeks, "week"), in_window(months, "month")

    for df, col in ((orders, "order_date"), (revenue, "order_date"), (cat, "order_date"), (prod, "order_date")):
        if not df.empty:
            df["week"] = df[col].map(week_start)
            df["month"] = df[col].map(month_start)

    anomalies: list[dict] = []
    for dimension, labels in (("store", store_labels), ("channel", CHANNEL_LABELS)):
        weekly = _pivot(orders, "week", dimension, "orders", weeks)
        anomalies += segment_vs_rest(weekly, labels, dimension, "week", cfg.volume_baseline_weeks,
                                     cfg.volume_min_pct, cfg.volume_min_z, cfg.volume_min_expected, eval_weeks)
    daily_channel = _pivot(orders, "order_date", "channel", "orders", days)
    anomalies += daily_spike(daily_channel, CHANNEL_LABELS, "channel", cfg, eval_days)
    anomalies += category_discount_excess(_pivot(cat, "week", "category", "gross", weeks),
                                          _pivot(cat, "week", "category", "discount", weeks), cfg, eval_weeks)
    anomalies += product_return_spike(
        _pivot(prod[prod.status == "completed"] if not prod.empty else prod, "month", "sku", "orders", months),
        _pivot(prod[prod.status == "returned"] if not prod.empty else prod, "month", "sku", "orders", months),
        product_labels, cfg, eval_months)
    weekly_revenue = (revenue.groupby("week")["net_revenue"].sum().astype(float).reindex(weeks, fill_value=0.0)
                      if not revenue.empty else pd.Series(dtype=float))
    anomalies += total_revenue_yoy(weekly_revenue, cfg, eval_weeks, data_min)

    rank = {"high": 0, "medium": 1, "low": 2}
    anomalies.sort(key=lambda a: (rank[a["severity"]], -abs(a["pct_diff"] or 0), a["period_start"]))
    counts = {s: sum(a["severity"] == s for a in anomalies) for s in rank}
    return {"data_range": {"start_date": data_min.isoformat(), "end_date": data_max.isoformat()},
            "evaluated_range": {"start_date": eval_start.isoformat(), "end_date": eval_end.isoformat()},
            "anomalies": anomalies, "counts": counts}
