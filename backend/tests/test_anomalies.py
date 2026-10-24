"""Anomaly detection: recall on the injected anomalies A1–A4 (sample_data/README.md), precision on the rest,
and unit tests for the statistical edge cases."""

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy.orm import sessionmaker

from app.demo.synthetic import write_csv
from app.services.anomaly_detection import detector as d
from app.services.ingestion.importer import run_import
from app.services.organization import get_demo_org_id

CFG = d.DetectionConfig()
INJECTED = {
    ("segment_volume_week", "S02", "2026-03-09"), ("segment_volume_week", "S02", "2026-03-16"),  # A1
    ("segment_spike_daily", "online", "2026-02-14"),  # A4
    ("product_returns_monthly", "ELE-002", "2026-04-01"),  # A3
}


def is_injected(a: dict) -> bool:
    if (a["detector"], a["segment_key"], a["period_start"]) in INJECTED:
        return True
    # A2: Beauty discounts during May 2026 (weeks overlapping May).
    return a["detector"] == "category_discount_weekly" and a["segment_key"] == "Beauty" and \
        "2026-04-27" <= a["period_start"] <= "2026-05-25"


@pytest.fixture(scope="module")
def synthetic_run(engine, tmp_path_factory):
    from tests.conftest import reset_tables

    reset_tables(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    path = tmp_path_factory.mktemp("data") / "retail.csv"
    write_csv(path)
    org_id = get_demo_org_id(db)
    assert run_import(db, org_id, path.name, path.read_bytes(), 500_000).status == "completed"
    result = d.detect(db, org_id, CFG)
    # Close before yielding: an open transaction would block later tests' TRUNCATE on PostgreSQL forever.
    db.close()
    return result


def find(result, detector, segment, start):
    return next((a for a in result["anomalies"] if a["detector"] == detector and a["segment_key"] == segment
                 and a["period_start"] == start), None)


def test_a1_store_drop_detected(synthetic_run):
    for week in ("2026-03-09", "2026-03-16"):
        a = find(synthetic_run, "segment_volume_week", "S02", week)
        assert a is not None, week
        assert a["direction"] == "down" and a["severity"] == "high" and a["pct_diff"] < -60


def test_a2_beauty_discount_spike_detected(synthetic_run):
    weeks = [a for a in synthetic_run["anomalies"] if a["detector"] == "category_discount_weekly"
             and a["segment_key"] == "Beauty" and a["period_start"].startswith("2026-05")]
    assert len(weeks) >= 3
    assert all(a["observed"] > 20 and a["expected"] < 5 for a in weeks[:3])


def test_a3_product_return_spike_detected(synthetic_run):
    a = find(synthetic_run, "product_returns_monthly", "ELE-002", "2026-04-01")
    assert a is not None and a["observed"] > 15 and a["direction"] == "up"


def test_a4_online_one_day_spike_detected(synthetic_run):
    a = find(synthetic_run, "segment_spike_daily", "online", "2026-02-14")
    assert a is not None and a["direction"] == "up" and a["severity"] == "high"


def test_precision_on_synthetic_data(synthetic_run):
    others = [a for a in synthetic_run["anomalies"] if not is_injected(a)]
    assert all(a["severity"] != "high" for a in others), others
    assert len(others) <= 3, others
    # No alerts for seasonal peaks the business expects: Black Friday week and December are company-wide.
    assert not any(a["period_start"] == "2025-11-24" for a in synthetic_run["anomalies"])


def test_every_anomaly_carries_required_fields(synthetic_run):
    for a in synthetic_run["anomalies"]:
        for field in ("metric", "observed", "expected", "abs_diff", "method", "severity", "period_start",
                      "period_end", "evidence", "note"):
            assert a[field] is not None, (field, a)


# ---------------------------------------------------------------- unit tests on the pure functions

def weekly_frame(values: dict[str, list[float]]) -> pd.DataFrame:
    weeks = [date(2026, 1, 5) + timedelta(weeks=i) for i in range(len(next(iter(values.values()))))]
    return pd.DataFrame(values, index=weeks)


def test_company_wide_surge_is_not_a_segment_anomaly():
    frame = weekly_frame({"A": [40] * 10 + [80], "B": [60] * 10 + [120]})  # everyone doubles: seasonality
    assert d.segment_vs_rest(frame, {}, "store", "week", 8, 35, 4, 15, [frame.index[-1]]) == []


def test_segment_drop_against_rest_is_flagged():
    frame = weekly_frame({"A": [40] * 10 + [10], "B": [60] * 11, "C": [50] * 11})
    [a] = d.segment_vs_rest(frame, {"A": "Store A"}, "store", "week", 8, 35, 4, 15, [frame.index[-1]])
    assert a["segment_key"] == "A" and a["direction"] == "down"  # B and C are not mirrored as spikes
    assert a["expected"] == 40 and a["observed"] == 10 and a["pct_diff"] == -75.0


def test_low_volume_segments_are_not_judged():
    frame = weekly_frame({"A": [4] * 10 + [0], "B": [60] * 11})  # expected 4 < minimum 15
    assert d.segment_vs_rest(frame, {}, "store", "week", 8, 35, 4, 15, [frame.index[-1]]) == []


def test_partial_periods_are_never_evaluated():
    weeks = pd.Index([date(2024, 12, 30), date(2025, 1, 6), date(2025, 1, 13)])
    # Data from Wed 1 Jan to Tue 14 Jan: only the week of 6 Jan is complete.
    assert d.complete_periods(weeks, "week", date(2025, 1, 1), date(2025, 1, 14)) == [date(2025, 1, 6)]


def test_yoy_ignores_incomplete_comparison_week():
    first = date(2024, 12, 30)  # partial: data starts 1 Jan 2025
    revenue = pd.Series({first: 100.0, first + timedelta(days=364): 1000.0})
    assert d.total_revenue_yoy(revenue, CFG, [first + timedelta(days=364)], date(2025, 1, 1)) == []


def test_daily_spike_requires_both_tests():
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(70)]
    base = pd.DataFrame({"online": [8.0] * 70, "in_store": [20.0] * 70}, index=days)
    surge = base.copy()
    surge.iloc[-1] = [24.0, 60.0]  # whole business triples: not a channel anomaly
    assert d.daily_spike(surge, {}, "channel", CFG, [days[-1]]) == []
    spike = base.copy()
    spike.iloc[-1] = [24.0, 20.0]  # only online triples
    [a] = d.daily_spike(spike, {}, "channel", CFG, [days[-1]])
    assert a["segment_key"] == "online" and a["observed"] == 24 and a["expected"] == 8


def test_return_spike_needs_volume():
    months = [date(2025, m, 1) for m in range(1, 9)]
    completed = pd.DataFrame({"P": [95.0] * 7 + [10.0]}, index=months)
    returned = pd.DataFrame({"P": [5.0] * 7 + [5.0]}, index=months)  # 33% but only 15 orders
    assert d.product_return_spike(completed, returned, {}, CFG, [months[-1]]) == []
    completed.iloc[-1, 0], returned.iloc[-1, 0] = 60.0, 30.0  # 33% of 90 orders vs 5% baseline
    [a] = d.product_return_spike(completed, returned, {}, CFG, [months[-1]])
    assert round(a["observed"], 1) == 33.3 and a["expected"] == 5.0


# ---------------------------------------------------------------- API

def test_anomaly_api_persists_runs(client, kpi_data):
    assert client.get("/api/v1/anomalies/latest").status_code == 404
    r = client.post("/api/v1/anomalies/detect", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["evaluated_range"]["start_date"] == "2024-12-20" and body["anomalies"] == []  # too little history
    assert client.get("/api/v1/anomalies/latest").json()["id"] == body["id"]
    assert client.get("/api/v1/anomalies/runs").json()["total"] == 1


def test_anomaly_api_validates_input(client, kpi_data):
    bad = client.post("/api/v1/anomalies/detect", json={"config": {"volume_min_pct": -5}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    swapped = client.post("/api/v1/anomalies/detect", json={"start_date": "2025-02-01", "end_date": "2025-01-01"})
    assert swapped.status_code == 422
    assert client.get("/api/v1/anomalies/latest?min_severity=urgent").status_code == 422
