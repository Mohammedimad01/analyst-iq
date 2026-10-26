"""Customer analytics (hand-calculated), workspace labels, reports/exports, automation auth and de-duplication,
read-only mode, organisation scoping and rate limiting."""

from datetime import date

import pytest

import app.models as m
from app.core.config import get_settings
from app.services.analytics import metrics
from app.services.analytics.metrics import Filters
from tests.conftest import add_order

JAN = {"start_date": "2025-01-01", "end_date": "2025-01-31"}
KEY = "test-automation-key-123"


@pytest.fixture
def customer_data(db, org_id):
    """January 2025, completed unless noted:
    C1: 10 + 20 (two orders; first ever order was 20 Dec 2024) | C2: 40 (first ever) | C3: cancelled only
    walk-in (no customer): 50.  Expected: active 2, new 1 (C2), repeat 1/2 = 50%, frequency 3/2 = 1.5,
    identified revenue 70 of 120 = 58.33%, revenue per customer 35, top 20% (1 of 2) = 40/70 = 57.14%.
    """
    s = m.Store(organization_id=org_id, store_code="S1", name="Store One")
    p = m.Product(organization_id=org_id, sku="P1", name="Widget", category="X")
    c1, c2, c3 = (m.Customer(organization_id=org_id, customer_code=f"C{i}", segment=seg)
                  for i, seg in ((1, "consumer"), (2, "business"), (3, None)))
    db.add_all([s, p, c1, c2, c3])
    db.flush()
    line = lambda price: [(p, 1, price, "0", "1.00")]  # noqa: E731
    add_order(db, org_id, "D1", date(2024, 12, 20), s, "online", "completed", line("5.00"), c1)
    add_order(db, org_id, "J1", date(2025, 1, 5), s, "online", "completed", line("10.00"), c1)
    add_order(db, org_id, "J2", date(2025, 1, 20), s, "online", "completed", line("20.00"), c1)
    add_order(db, org_id, "J3", date(2025, 1, 10), s, "online", "completed", line("40.00"), c2)
    add_order(db, org_id, "J4", date(2025, 1, 11), s, "online", "cancelled", line("99.00"), c3)
    add_order(db, org_id, "J5", date(2025, 1, 12), s, "in_store", "completed", line("50.00"))
    db.commit()
    return org_id


# ---------------------------------------------------------------- customers

def test_customer_metrics_hand_calculated(db, customer_data):
    f = Filters(date(2025, 1, 1), date(2025, 1, 31))
    s = metrics.customer_summary(db, customer_data, f)
    assert s["active_customers"] == 2 and s["new_customers"] == 1
    assert float(s["repeat_customer_rate_pct"]) == 50.0
    assert float(s["orders_per_customer"]) == 1.5
    assert float(s["revenue_per_customer"]) == 35.0
    assert float(s["identified_revenue_share_pct"]) == 58.33


def test_customer_endpoint(client, customer_data):
    body = client.get("/api/v1/analytics/customers", params=JAN).json()
    kpis = {k["key"]: k for k in body["kpis"]}
    assert kpis["active_customers"]["value"] == 2 and kpis["active_customers"]["previous"] == 1
    assert body["concentration"] == {"top_fraction_pct": 20, "top_count": 1, "item_count": 2, "share_pct": 57.14}
    assert [t["customer_code"] for t in body["top_customers"]] == ["C2", "C1"]
    assert {s["segment"]: s["customers"] for s in body["segments"]} == {"business": 1, "consumer": 1}
    assert sum(p["new_customers"] for p in body["trend"]["points"]) == 1
    # Only 31 days of data before January: the endpoint says new-vs-returning is unreliable.
    assert body["history_days_before_period"] == 12 and any("counted as new" in w for w in body["warnings"])


def test_customer_metrics_with_no_identified_customers(client, kpi_data):
    body = client.get("/api/v1/analytics/customers", params=JAN).json()
    kpis = {k["key"]: k["value"] for k in body["kpis"]}
    assert kpis["active_customers"] == 0 and kpis["repeat_customer_rate_pct"] is None
    assert kpis["identified_revenue_share_pct"] == 0 and body["top_customers"] == []
    assert body["concentration"]["share_pct"] is None


def test_breakdown_reports_concentration(client, kpi_data):
    body = client.get("/api/v1/analytics/breakdown/category", params=JAN).json()
    # X 58 and Y 20: top 20% of 2 groups is 1 group = 58/78.
    assert body["concentration"]["share_pct"] == 74.36


# ---------------------------------------------------------------- workspace and read-only mode

def test_workspace_reflects_data_source(client, db, org_id):
    assert client.get("/api/v1/workspace").json()["data_kind"] == "none"
    csv = ("order_id,order_date,store_id,channel,product_sku,product_name,category,quantity,unit_price,unit_cost,"
           "status\nA1,2025-03-01,S1,in_store,P1,W,X,1,10,6,completed\n")
    client.post("/api/v1/data/imports", files={"file": ("mine.csv", csv.encode())})
    w = client.get("/api/v1/workspace").json()
    assert w["data_kind"] == "imported" and w["last_import"]["source"] == "upload"
    from app.services.ingestion.importer import run_import
    demo = csv.replace("A1,", "B1,")
    run_import(db, org_id, "retail_sample.csv", demo.encode(), 1000, source="synthetic_demo")
    w = client.get("/api/v1/workspace").json()
    assert w["data_kind"] == "mixed" and w["synthetic_orders"] == 1 and w["imported_orders"] == 1
    assert w["organization_name"] == get_settings().organization_name and w["single_organization"] is True


def test_read_only_mode_blocks_uploads(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "read_only_mode", True)
    r = client.post("/api/v1/data/imports", files={"file": ("x.csv", b"a,b\n1,2\n")})
    assert r.status_code == 403 and r.json()["error"]["code"] == "read_only"


def test_queries_are_scoped_to_the_organisation(client, db, kpi_data):
    other = m.Organization(name="Other", slug="other")
    db.add(other)
    db.flush()
    s = m.Store(organization_id=other.id, store_code="Z9", name="Other store")
    p = m.Product(organization_id=other.id, sku="Z", name="Other", category="Other")
    db.add_all([s, p])
    db.flush()
    add_order(db, other.id, "Z1", date(2025, 1, 15), s, "online", "completed", [(p, 1, "999.00", "0", "1.00")])
    db.commit()
    body = client.get("/api/v1/dashboard/overview", params=JAN).json()
    assert {k["key"]: k["value"] for k in body["kpis"]}["net_revenue"] == 78.0
    assert "Z9" not in {s["code"] for s in client.get("/api/v1/dashboard/filters").json()["stores"]}


# ---------------------------------------------------------------- reports and exports

def test_pdf_and_csv_reports_use_dashboard_numbers(client, kpi_data):
    pdf = client.post("/api/v1/reports/generate", json={"type": "executive", "format": "pdf", **JAN})
    assert pdf.status_code == 201, pdf.json()
    meta = pdf.json()
    assert meta["contains_synthetic"] is False and meta["filename"].endswith(".pdf")
    file = client.get(f"/api/v1/reports/{meta['id']}/download")
    assert file.content.startswith(b"%PDF") and "attachment" in file.headers["content-disposition"]
    csv = client.post("/api/v1/reports/generate", json={"type": "sales", "format": "csv", **JAN}).json()
    text = client.get(f"/api/v1/reports/{csv['id']}/download").content.decode("utf-8-sig")
    assert "Net Revenue,78.00,10.00,680.00" in text and "SYNTHETIC" not in text
    listing = client.get("/api/v1/reports").json()
    assert listing["total"] == 2 and listing["items"][0]["file_format"] == "csv"


@pytest.mark.parametrize("report_type", ["executive", "sales", "product", "store", "customer", "profitability"])
def test_every_report_type_renders(client, kpi_data, report_type):
    r = client.post("/api/v1/reports/generate", json={"type": report_type, "format": "pdf", **JAN})
    assert r.status_code == 201, r.json()


def test_synthetic_reports_say_so(client, db, org_id):
    from app.services.ingestion.importer import run_import
    csv = ("order_id,order_date,store_id,channel,product_sku,product_name,category,quantity,unit_price,unit_cost,"
           "status\nA1,2025-01-10,S1,in_store,P1,W,X,1,10,6,completed\n")
    run_import(db, org_id, "retail_sample.csv", csv.encode(), 1000, source="synthetic_demo")
    meta = client.post("/api/v1/reports/generate", json={"type": "sales", "format": "csv", **JAN}).json()
    assert meta["contains_synthetic"] is True
    assert "SYNTHETIC DEMO DATA" in client.get(f"/api/v1/reports/{meta['id']}/download").content.decode("utf-8-sig")


def test_report_validation(client, kpi_data):
    empty = client.post("/api/v1/reports/generate", json={"type": "sales", "start_date": "2030-01-01",
                                                          "end_date": "2030-01-31"})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_report"
    assert client.post("/api/v1/reports/generate", json={"type": "nope", **JAN}).status_code == 422
    assert client.post("/api/v1/reports/generate", json={"type": "sales"}).status_code == 422
    assert client.get("/api/v1/reports/999/download").status_code == 404


def test_csv_export_blocks_formula_injection(client, db, org_id):
    s = m.Store(organization_id=org_id, store_code="S1", name="Store")
    p = m.Product(organization_id=org_id, sku="=EVIL", name='=HYPERLINK("http://x","click")', category="+cmd")
    db.add_all([s, p])
    db.flush()
    add_order(db, org_id, "O1", date(2025, 1, 10), s, "online", "completed", [(p, 1, "10.00", "0", "4.00")])
    db.commit()
    text = client.get("/api/v1/exports/products.csv", params=JAN).content.decode("utf-8-sig")
    assert "'=HYPERLINK" in text and "'=EVIL" in text and ",=" not in text
    cats = client.get("/api/v1/exports/categories.csv", params=JAN).content.decode("utf-8-sig")
    assert cats.splitlines()[1].startswith("'+cmd,10.00")  # numbers stay raw numbers


def test_exports_validate_dataset_and_filters(client, kpi_data):
    assert client.get("/api/v1/exports/secrets.csv", params=JAN).status_code == 422
    assert client.get("/api/v1/exports/kpis.csv", params={"start_date": "2025-02-01",
                                                          "end_date": "2025-01-01"}).status_code == 422
    assert client.get("/api/v1/exports/trend.csv", params=JAN).status_code == 200


# ---------------------------------------------------------------- automation

@pytest.fixture
def automation_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "automation_api_key", KEY)
    return {"X-API-Key": KEY}


def test_automation_requires_configured_key(client, kpi_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "automation_api_key", "")
    r = client.post("/api/v1/automation/kpi-summary", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "automation_disabled"
    monkeypatch.setattr(get_settings(), "automation_api_key", KEY)
    assert client.post("/api/v1/automation/kpi-summary", json={}).status_code == 401
    assert client.post("/api/v1/automation/kpi-summary", json={}, headers={"X-API-Key": "wrong"}).status_code == 401


def test_pasted_key_whitespace_and_quotes_are_ignored(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("AUTOMATION_API_KEY", f' "{KEY}"\n')
    assert Settings(_env_file=None).automation_api_key == KEY


def test_kpi_summary_and_delivery_dedupe(client, kpi_data, automation_key):
    body = {"period": "last_30_days", "anchor": "latest_data"}
    first = client.post("/api/v1/automation/kpi-summary", json=body, headers=automation_key).json()
    assert first["period"] == {"start_date": "2025-01-03", "end_date": "2025-02-01", "days": 30}
    assert first["should_notify"] is True and "Net Revenue:" in first["message"]
    rec = client.post("/api/v1/automation/deliveries", headers=automation_key,
                      json={"workflow": "kpi_summary", "item_keys": first["delivery_keys"]}).json()
    assert rec == {"workflow": "kpi_summary", "recorded": 1, "already_recorded": 0}
    again = client.post("/api/v1/automation/deliveries", headers=automation_key,
                        json={"workflow": "kpi_summary", "item_keys": first["delivery_keys"]}).json()
    assert again["recorded"] == 0 and again["already_recorded"] == 1
    second = client.post("/api/v1/automation/kpi-summary", json=body, headers=automation_key).json()
    assert second["should_notify"] is False


def test_anomaly_alerts_only_return_undelivered(client, db, kpi_data, automation_key):
    anomaly = {"key": "k1", "detector": "x", "metric": "orders", "metric_label": "Completed orders",
               "dimension": "store", "segment_key": "S1", "segment_label": "Store One", "grain": "week",
               "period_start": "2025-01-06", "period_end": "2025-01-12", "observed": 1, "expected": 9,
               "abs_diff": -8, "pct_diff": -88.9, "z_score": -5, "direction": "down", "severity": "high",
               "method": "m", "evidence": {}, "note": "n"}
    db.add(m.AnalysisRun(organization_id=kpi_data, analysis_type="anomaly_detection", params={},
                         result={"anomalies": [anomaly], "counts": {"high": 1}}))
    db.commit()
    req = {"min_severity": "high", "run_detection": False}
    first = client.post("/api/v1/automation/anomaly-alerts", json=req, headers=automation_key).json()
    assert first["should_notify"] and first["delivery_keys"] == ["k1"] and "Store One" in first["message"]
    client.post("/api/v1/automation/deliveries", headers=automation_key,
                json={"workflow": "anomaly_alert", "item_keys": ["k1"]})
    second = client.post("/api/v1/automation/anomaly-alerts", json=req, headers=automation_key).json()
    assert second["should_notify"] is False and second["already_delivered"] == 1


def test_scheduled_report_is_idempotent(client, kpi_data, automation_key):
    req = {"type": "sales", "format": "csv", "period": "previous_month", "anchor": "latest_data"}
    first = client.post("/api/v1/automation/reports", json=req, headers=automation_key).json()
    assert first["reused"] is False and first["report"]["params"]["start_date"] == "2025-01-01"
    second = client.post("/api/v1/automation/reports", json=req, headers=automation_key).json()
    assert second["reused"] is True and second["report"]["id"] == first["report"]["id"]
    file = client.get(first["download_path"], headers=automation_key)
    assert file.status_code == 200 and b"Net Revenue" in file.content
    assert client.get(first["download_path"]).status_code == 401


def test_latest_import_notification(client, automation_key):
    assert client.get("/api/v1/automation/imports/latest", headers=automation_key).json()["should_notify"] is False
    csv = ("order_id,order_date,store_id,channel,product_sku,product_name,category,quantity,unit_price,unit_cost,"
           "status\nA1,2025-03-01,S1,in_store,P1,W,X,1,10,6,completed\n")
    client.post("/api/v1/data/imports", files={"file": ("mine.csv", csv.encode())})
    latest = client.get("/api/v1/automation/imports/latest", headers=automation_key).json()
    assert latest["should_notify"] and latest["import"]["status"] == "completed" and "mine.csv" in latest["message"]


# ---------------------------------------------------------------- rate limiting

def test_expensive_endpoints_are_rate_limited(client, kpi_data):
    statuses = [client.post("/api/v1/anomalies/detect", json={}).status_code for _ in range(11)]
    assert statuses[:10] == [201] * 10 and statuses[10] == 429
