from sqlalchemy.exc import OperationalError

from app.api.routes import dashboard

JAN = {"start_date": "2025-01-01", "end_date": "2025-01-31"}


def test_health(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert isinstance(body["gemini_configured"], bool)


def test_filters_empty_then_populated(client, db):
    assert client.get("/api/v1/dashboard/filters").json()["has_data"] is False


def test_filter_options(client, kpi_data):
    body = client.get("/api/v1/dashboard/filters").json()
    assert body["has_data"] and body["date_min"] == "2024-12-20" and body["date_max"] == "2025-02-01"
    assert [s["code"] for s in body["stores"]] == ["S1", "S2"]
    assert body["categories"] == ["X", "Y"] and body["channels"] == ["in_store", "online"]


def test_overview_matches_kpi_engine(client, kpi_data):
    r = client.get("/api/v1/dashboard/overview", params=JAN)
    assert r.status_code == 200
    body = r.json()
    kpis = {k["key"]: k for k in body["kpis"]}
    assert kpis["net_revenue"]["value"] == 78.0 and kpis["net_revenue"]["unit"] == "currency"
    assert kpis["gross_margin_pct"]["value"] == 34.62
    assert body["comparison_period"] == {"start_date": "2024-12-01", "end_date": "2024-12-31", "days": 31}
    assert body["trend"]["grain"] == "day" and len(body["trend"]["points"]) == 31
    assert body["top_products"][0]["key"] == "P1"
    assert {r["key"] for r in body["by_channel"]} == {"in_store", "online"}


def test_overview_respects_filters(client, kpi_data):
    body = client.get("/api/v1/dashboard/overview", params={**JAN, "store": "S2"}).json()
    kpis = {k["key"]: k for k in body["kpis"]}
    assert kpis["net_revenue"]["value"] == 30.0
    assert [r["key"] for r in body["by_store"]] == ["S2"]
    assert sum(p["net_revenue"] for p in body["trend"]["points"]) == 30.0


def test_empty_result_has_null_ratios(client, kpi_data):
    body = client.get("/api/v1/dashboard/overview", params={"start_date": "2030-01-01", "end_date": "2030-01-31"}).json()
    kpis = {k["key"]: k for k in body["kpis"]}
    assert kpis["net_revenue"]["value"] == 0 and kpis["gross_margin_pct"]["value"] is None
    assert body["top_products"] == []


def test_sales_and_breakdown(client, kpi_data):
    sales = client.get("/api/v1/analytics/sales", params={**JAN, "grain": "week"}).json()
    assert sales["trend"]["grain"] == "week"
    page = client.get("/api/v1/analytics/breakdown/product",
                      params={**JAN, "sort": "gross_margin_pct", "order": "asc", "limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["items"][0]["key"] == "P2"  # 25% < 37.93%


def test_validation_errors_use_envelope(client):
    cases = [
        ({"start_date": "2025-02-01", "end_date": "2025-01-01"}, "end_date must be on or after start_date"),
        ({"start_date": "2020-01-01", "end_date": "2025-01-01"}, "limited to"),
        ({"start_date": "2025-01-01"}, None),
        ({**JAN, "channel": "fax"}, None),
    ]
    for params, message in cases:
        r = client.get("/api/v1/dashboard/overview", params=params)
        assert r.status_code == 422
        err = r.json()["error"]
        assert err["code"] == "validation_error"
        if message:
            assert message in err["message"]
    assert client.get("/api/v1/analytics/breakdown/customer", params=JAN).status_code == 422


def test_database_failure_returns_503_without_internals(client, kpi_data, monkeypatch):
    def boom(*args, **kwargs):
        raise OperationalError("SELECT secret", {}, Exception("password=hunter2"))

    monkeypatch.setattr(dashboard.metrics, "kpis_with_comparison", boom)
    r = client.get("/api/v1/dashboard/overview", params=JAN)
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
    assert "hunter2" not in r.text and "SELECT" not in r.text
