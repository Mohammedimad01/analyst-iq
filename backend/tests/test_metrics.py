"""KPI formulas against the hand-built dataset in conftest.kpi_data.

January 2025 (current period), recognised = completed orders O1, O2, O7:
  O1: P1 2×10 − 2 disc = 18 net, cogs 12 | P2 1×20 = 20 net, cogs 15   -> net 38, cogs 27
  O2: P1 3×10 = 30 net, cogs 18
  O7: P1 1×10 = 10 net, cogs 6 (31 Jan: inclusive end boundary)
  gross 80, discounts 2, net 78, cogs 51, profit 27, units 7, orders 3
  O3 cancelled, O4 returned (excluded from revenue); O6 is 1 Feb (outside); O5 is December (previous period).
"""

from datetime import date
from decimal import Decimal as D

from app.services.analytics import metrics
from app.services.analytics.metrics import KPI_DEFS, Filters

JAN = Filters(date(2025, 1, 1), date(2025, 1, 31))


def test_summary_core_kpis(db, kpi_data):
    s = metrics.summary(db, kpi_data, JAN)
    assert s["gross_sales"] == D("80.00")
    assert s["discounts"] == D("2.00")
    assert s["net_revenue"] == D("78.00")
    assert s["gross_profit"] == D("27.00")
    assert s["gross_margin_pct"] == D("34.62")  # 27 / 78
    assert s["orders"] == 3  # O1 has two lines but counts once
    assert s["avg_order_value"] == D("26.00")
    assert s["units_sold"] == 7
    assert s["discount_rate_pct"] == D("2.50")  # 2 / 80
    assert s["return_rate_pct"] == D("25.00")  # 1 returned / (3 completed + 1 returned)
    assert s["cancellation_rate_pct"] == D("20.00")  # 1 of 5 orders in January


def test_previous_period_is_equal_length_and_adjacent():
    prev = JAN.previous_period()
    assert (prev.start_date, prev.end_date) == (date(2024, 12, 1), date(2024, 12, 31))
    assert prev.days == JAN.days == 31


def test_comparison_and_sentiment(db, kpi_data):
    kpis = {k["key"]: k for k in metrics.kpis_with_comparison(db, kpi_data, JAN)}
    net = kpis["net_revenue"]
    assert (net["value"], net["previous"], net["abs_change"]) == (D("78.00"), D("10.00"), D("68.00"))
    assert net["pct_change"] == D("680.00")
    assert (net["direction"], net["sentiment"]) == ("up", "positive")
    # December had no returns: rate goes 0 -> 25, which is bad news.
    ret = kpis["return_rate_pct"]
    assert ret["abs_change"] == D("25.00") and ret["pct_change"] is None
    assert ret["sentiment"] == "negative"


def test_compare_handles_zero_and_missing_baselines():
    net_def = next(k for k in KPI_DEFS if k.key == "net_revenue")
    assert metrics.compare(net_def, D("5"), D("0"))["pct_change"] is None
    missing = metrics.compare(net_def, D("5"), None)
    assert missing["abs_change"] is None and missing["direction"] == "flat"
    down = metrics.compare(net_def, D("-5"), D("10"))  # negative adjustment
    assert down["pct_change"] == D("-150.00") and down["sentiment"] == "negative"


def test_empty_period_returns_zero_and_null_ratios(db, kpi_data):
    s = metrics.summary(db, kpi_data, Filters(date(2030, 1, 1), date(2030, 1, 31)))
    assert s["net_revenue"] == D("0.00") and s["orders"] == 0 and s["units_sold"] == 0
    assert s["gross_margin_pct"] is None and s["avg_order_value"] is None
    assert s["return_rate_pct"] is None and s["cancellation_rate_pct"] is None


def test_category_filter_counts_only_matching_lines(db, kpi_data):
    s = metrics.summary(db, kpi_data, Filters(JAN.start_date, JAN.end_date, categories=("X",)))
    assert s["net_revenue"] == D("58.00")  # 18 + 30 + 10
    assert s["gross_profit"] == D("22.00")  # 58 − 36
    assert s["orders"] == 3
    assert s["cancellation_rate_pct"] == D("0.00")  # O3 only has category Y


def test_store_and_channel_filters(db, kpi_data):
    for f in (Filters(JAN.start_date, JAN.end_date, stores=("S2",)),
              Filters(JAN.start_date, JAN.end_date, channels=("online",))):
        s = metrics.summary(db, kpi_data, f)
        assert s["net_revenue"] == D("30.00") and s["orders"] == 1
        assert s["return_rate_pct"] == D("50.00")


def test_date_boundaries_are_inclusive(db, kpi_data):
    assert metrics.summary(db, kpi_data, Filters(date(2025, 1, 31), date(2025, 1, 31)))["net_revenue"] == D("10.00")
    assert metrics.summary(db, kpi_data, Filters(date(2025, 2, 1), date(2025, 2, 1)))["net_revenue"] == D("20.00")


def test_trend_buckets_fill_gaps_and_sum_to_total(db, kpi_data):
    for grain in ("day", "week", "month"):
        t = metrics.trend(db, kpi_data, JAN, grain)
        assert sum(p["net_revenue"] for p in t["points"]) == D("78.00")
        assert sum(p["orders"] for p in t["points"]) == 3
    days = metrics.trend(db, kpi_data, JAN, "day")["points"]
    assert len(days) == 31 and not any(p["partial"] for p in days)
    weeks = metrics.trend(db, kpi_data, JAN, "week")["points"]
    assert weeks[0]["period_start"] == date(2024, 12, 30) and weeks[0]["partial"]  # 1 Jan 2025 is a Wednesday
    assert weeks[-1]["period_start"] == date(2025, 1, 27) and weeks[-1]["partial"]
    month = metrics.trend(db, kpi_data, JAN, "month")["points"]
    assert len(month) == 1 and month[0]["period_start"] == date(2025, 1, 1) and not month[0]["partial"]


def test_auto_grain():
    assert metrics.auto_grain(JAN) == "day"
    assert metrics.auto_grain(Filters(date(2025, 1, 1), date(2025, 6, 30))) == "week"
    assert metrics.auto_grain(Filters(date(2025, 1, 1), date(2025, 12, 31))) == "month"


def test_breakdown_by_category_and_share(db, kpi_data):
    rows = {r["key"]: r for r in metrics.breakdown(db, kpi_data, JAN, "category")}
    assert rows["X"]["net_revenue"] == D("58.00") and rows["X"]["share_pct"] == D("74.36")
    assert rows["Y"]["net_revenue"] == D("20.00") and rows["Y"]["gross_margin_pct"] == D("25.00")
    assert rows["X"]["orders"] == 3 and rows["Y"]["orders"] == 1


def test_breakdown_sort_puts_undefined_ratios_last():
    rows = [{"key": "a", "m": None}, {"key": "b", "m": D("5")}, {"key": "c", "m": D("9")}]
    assert [r["key"] for r in metrics.sort_rows(rows, "m", True)] == ["c", "b", "a"]
    assert [r["key"] for r in metrics.sort_rows(rows, "m", False)] == ["b", "c", "a"]


def test_change_drivers_explain_total_change(db, kpi_data):
    rows = {r["key"]: r for r in metrics.change_drivers(db, kpi_data, JAN, "category")}
    # December: X = 10, Y = 0. January: X = 58, Y = 20. Total change = +68.
    assert rows["X"]["change"] == D("48.00") and rows["X"]["change_pct"] == D("480.00")
    assert rows["Y"]["previous_net_revenue"] == D("0.00") and rows["Y"]["change_pct"] is None
    assert rows["X"]["share_of_total_change_pct"] == D("70.59") and rows["Y"]["share_of_total_change_pct"] == D("29.41")
