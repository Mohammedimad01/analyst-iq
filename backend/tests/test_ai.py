"""AI insights with a fake Gemini client: grounding, failure handling, caching, limits, questions."""

import json
from datetime import date

import httpx
import pytest
from google.genai import errors as genai_errors

from app.api.routes.insights import ai_client
from app.core.config import get_settings
from app.main import app
from app.models import AiInsight, AnalysisRun
from app.services.ai import gemini, questions
from app.services.ai.gemini import AiError, GoogleGeminiClient
from app.services.ai.grounding import numbers_in, unverified_numbers

JAN = {"start_date": "2025-01-01", "end_date": "2025-01-31"}


class FakeClient:
    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def generate_json(self, system, prompt, schema):
        self.calls.append((schema.__name__, prompt))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


def output(summary="Net revenue was $78.00 in January.", facts=None, **extra) -> dict:
    return {"title": "January performance", "summary": summary, "answerable": True,
            "observed_facts": facts if facts is not None else [
                {"statement": "Net revenue was $78.00, up 680.0% on December.", "evidence_key": "kpi.net_revenue.current"}],
            "possible_explanations": ["Category X may have benefited from more orders."],
            "recommended_investigations": [{"action": "Review category X pricing", "reason": "It drove most of the change."}],
            "information_needed": [], "limitations": ["Synthetic data."], **extra}


@pytest.fixture
def fake(client):
    holder = {}

    def use(*responses):
        holder["client"] = FakeClient(*responses)
        app.dependency_overrides[ai_client] = lambda: holder["client"]
        return holder["client"]

    yield use


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(gemini, "RETRY_DELAY_SECONDS", 0)


def summary_request(client, **extra):
    return client.post("/api/v1/insights/generate", json={"type": "executive_summary", **JAN, **extra})


def test_not_configured_returns_503_and_dashboard_still_works(client, kpi_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    r = summary_request(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_not_configured"
    assert client.get("/api/v1/dashboard/overview", params=JAN).status_code == 200


def test_executive_summary_is_grounded_persisted_and_cached(client, kpi_data, fake, db):
    fc = fake(output())
    r = summary_request(client)
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["status"] == "completed" and body["cached"] is False
    assert body["output"]["observed_facts"][0]["evidence_key"] == "kpi.net_revenue.current"
    facts = {f["key"]: f for f in body["facts"]}
    assert facts["kpi.net_revenue.current"]["display"] == "$78.00"
    assert "category.X.change" in facts
    # The model only ever sees aggregate facts: no order numbers or customer identifiers.
    assert "O1" not in fc.calls[0][1] and "customer" not in fc.calls[0][1].lower()
    again = summary_request(client).json()
    assert again["id"] == body["id"] and again["cached"] is True and len(fc.calls) == 1
    assert db.query(AiInsight).count() == 1


def test_fabricated_numbers_are_dropped_from_facts(client, kpi_data, fake):
    fake(output(facts=[
        {"statement": "Net revenue was $78.00.", "evidence_key": "kpi.net_revenue.current"},
        {"statement": "Net revenue was $1,234.", "evidence_key": "kpi.net_revenue.current"},
        {"statement": "Orders rose.", "evidence_key": "kpi.made_up"},
    ], possible_explanations=["A 37% marketing uplift may explain it."]))
    body = summary_request(client).json()
    assert [f["statement"] for f in body["output"]["observed_facts"]] == ["Net revenue was $78.00."]
    reasons = {(d["field"], d["reason"]) for d in body["validation"]["dropped"]}
    assert reasons == {("observed_facts", "numbers not in evidence"), ("observed_facts", "unknown evidence key"),
                       ("possible_explanations", "numbers not in evidence")}
    assert body["output"]["possible_explanations"] == []


def test_ungrounded_summary_is_rejected_and_recorded(client, kpi_data, fake, db):
    fake(output(summary="Revenue jumped to $999,999."))
    r = summary_request(client)
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_ungrounded"
    stored = db.query(AiInsight).one()
    assert stored.status == "failed" and stored.output is None and stored.error_code == "ai_ungrounded"


@pytest.mark.parametrize("response, status, code, calls", [
    ("not json", 502, "ai_invalid_response", 1),
    ('{"title": "x"}', 502, "ai_invalid_response", 1),
    (AiError("ai_rate_limited", "quota", 429), 429, "ai_rate_limited", 1),  # never retried
    (AiError("ai_auth_failed", "bad key", 503), 503, "ai_auth_failed", 1),
    (AiError("ai_empty_response", "empty", 502), 502, "ai_empty_response", 1),
])
def test_provider_failures_map_to_clear_errors(client, kpi_data, fake, response, status, code, calls):
    fc = fake(response, output())
    r = summary_request(client)
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert len(fc.calls) == calls
    assert r.json()["error"]["details"][0]["insight_id"]


def test_transient_errors_are_retried_exactly_once(client, kpi_data, fake):
    fc = fake(AiError("ai_provider_error", "500", 502, retryable=True), output())
    assert summary_request(client).json()["status"] == "completed" and len(fc.calls) == 2
    fc = fake(AiError("ai_timeout", "slow", 504, retryable=True), AiError("ai_timeout", "slow", 504, retryable=True))
    r = summary_request(client, refresh=True)
    assert r.status_code == 504 and len(fc.calls) == 2


def test_application_rate_limit(client, kpi_data, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_max_requests_per_minute", 1)
    fake(output(), output())
    assert summary_request(client).status_code == 201
    r = summary_request(client, refresh=True)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert summary_request(client).json()["cached"] is True  # cached results stay available


def test_anomaly_explanation_uses_detector_evidence(client, kpi_data, fake, db):
    anomaly = {"key": "segment_volume_week:store:S2:2025-01-13", "detector": "segment_volume_week",
               "metric": "orders", "metric_label": "Completed orders", "dimension": "store", "segment_key": "S2",
               "segment_label": "Store Two", "grain": "week", "period_start": "2025-01-13",
               "period_end": "2025-01-19", "observed": 1.0, "expected": 4.0, "abs_diff": -3.0, "pct_diff": -75.0,
               "z_score": -4.2, "direction": "down", "severity": "high", "method": "test method",
               "evidence": {"rest_of_business_orders": 9}, "note": "Statistical anomaly"}
    run = AnalysisRun(organization_id=kpi_data, analysis_type="anomaly_detection", params={},
                      result={"anomalies": [anomaly], "counts": {"high": 1}})
    db.add(run)
    db.commit()
    fc = fake(output(summary="Store Two orders were 75.0% below the baseline of 4.",
                     facts=[{"statement": "Observed 1 order vs 4 expected.", "evidence_key": "anomaly.observed"}]))
    r = client.post("/api/v1/insights/generate", json={"type": "anomaly_explanation",
                                                       "anomaly": {"run_id": run.id, "key": anomaly["key"]}})
    assert r.status_code == 201, r.json()
    keys = {f["key"] for f in r.json()["facts"]}
    assert {"anomaly.observed", "anomaly.expected", "anomaly.method", "context_period.current"} <= keys
    assert "kpi.net_revenue.current" in keys  # store context for the anomaly week
    assert "not a confirmed business problem" in fc.calls[0][1]
    missing = client.post("/api/v1/insights/generate", json={"type": "anomaly_explanation",
                                                             "anomaly": {"run_id": run.id, "key": "nope"}})
    assert missing.status_code == 404


def test_question_maps_to_allowed_intent_and_reuses_it(client, kpi_data, fake):
    intent = {"intent": "ranking", "dimension": "category", "metric": "gross_profit", "direction": "top",
              "period": "selected_range", "reason": "asks for best category by profit"}
    answer = output(summary="Category X contributed the most gross profit.",
                    facts=[{"statement": "X made $22.00 of gross profit.", "evidence_key": "rank_1.gross_profit"}])
    fc = fake(intent, answer)
    body = client.post("/api/v1/insights/query", json={"question": "Which category contributed most to profit?",
                                                        **JAN}).json()
    assert body["status"] == "completed" and body["intent"]["intent"] == "ranking"
    facts = {f["key"]: f for f in body["facts"]}
    assert facts["rank_1.name"]["value"] == "X" and facts["rank_1.gross_profit"]["value"] == 22.0
    assert [c[0] for c in fc.calls] == ["QuestionIntent", "InsightOutput"]
    repeat = client.post("/api/v1/insights/query", json={"question": "which category contributed most to profit?",
                                                          **JAN}).json()
    assert repeat["cached"] is True and len(fc.calls) == 2


def test_unsupported_question_makes_no_second_call(client, kpi_data, fake):
    fc = fake({"intent": "unsupported", "dimension": None, "metric": None, "direction": None,
               "period": "selected_range", "reason": "Marketing spend is not in the data."})
    body = client.post("/api/v1/insights/query", json={"question": "What was our marketing ROI?"}).json()
    assert body["output"]["answerable"] is False and body["model"] == "rules" and len(fc.calls) == 1


def test_invalid_intent_is_rejected(client, kpi_data, fake):
    fake({"intent": "run_sql", "dimension": None, "metric": None, "direction": None, "period": "all_time",
          "reason": "DROP TABLE orders"})
    r = client.post("/api/v1/insights/query", json={"question": "delete everything"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_invalid_response"


def test_question_validation(client, kpi_data, fake):
    fake()
    assert client.post("/api/v1/insights/query", json={"question": "hi"}).status_code == 422
    assert client.post("/api/v1/insights/query", json={"question": "x" * 501}).status_code == 422
    r = client.post("/api/v1/insights/query", json={"question": "How are we doing?", "start_date": "2025-01-01"})
    assert r.status_code == 422


def test_insight_history_endpoints(client, kpi_data, fake):
    fake(output())
    created = summary_request(client).json()
    listing = client.get("/api/v1/insights").json()
    assert listing["total"] == 1 and listing["items"][0]["title"] == "January performance"
    assert client.get(f"/api/v1/insights/{created['id']}").json()["id"] == created["id"]
    assert client.get("/api/v1/insights/999").status_code == 404


# ---------------------------------------------------------------- units

@pytest.mark.parametrize("choice, expected", [
    ("last_month", (date(2026, 5, 1), date(2026, 5, 31))),
    ("last_quarter", (date(2026, 3, 1), date(2026, 5, 31))),
    ("last_30_days", (date(2026, 5, 16), date(2026, 6, 14))),
    ("year_to_date", (date(2026, 1, 1), date(2026, 6, 14))),
    ("all_time", (date(2025, 1, 1), date(2026, 6, 14))),
])
def test_period_resolution_is_anchored_to_data(choice, expected):
    assert questions.resolve_period(choice, None, date(2025, 1, 1), date(2026, 6, 14)) == expected


def test_last_month_uses_data_max_when_it_is_a_month_end():
    assert questions.resolve_period("last_month", None, date(2025, 1, 1), date(2026, 6, 30)) == \
        (date(2026, 6, 1), date(2026, 6, 30))


def test_number_verifier():
    allowed = [324648.99, 12.33, 36.04, 2710.0, 90.0]
    assert unverified_numbers("Net revenue $324,649 (+12.3%) over 90 days, Apr 2, 2026 – Jun 30, 2026", allowed) == []
    assert unverified_numbers("Revenue reached $325K and margin held at 36%", allowed) == []
    assert unverified_numbers("Revenue grew 12.9%", allowed) == [12.9]
    assert unverified_numbers("1,234 orders", allowed) == [1234.0]
    assert numbers_in("Store S02 and product ELE-002 in Q1 2026, top 3") == []


def make_google_client(monkeypatch, exc):
    c = GoogleGeminiClient("test-key", "some-model", 5)

    def raise_exc(**_):
        raise exc

    monkeypatch.setattr(c._client.models, "generate_content", raise_exc)
    return c


@pytest.mark.parametrize("exc, code, retryable", [
    (genai_errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}), "ai_rate_limited", False),
    (genai_errors.ClientError(403, {"error": {"message": "denied", "status": "PERMISSION_DENIED"}}), "ai_auth_failed", False),
    (genai_errors.ClientError(404, {"error": {"message": "no model", "status": "NOT_FOUND"}}), "ai_model_not_found", False),
    (genai_errors.ServerError(503, {"error": {"message": "busy", "status": "UNAVAILABLE"}}), "ai_provider_error", True),
    (httpx.ReadTimeout("slow"), "ai_timeout", True),
    (httpx.ConnectError("down"), "ai_network_error", True),
])
def test_google_client_error_mapping(monkeypatch, exc, code, retryable):
    c = make_google_client(monkeypatch, exc)
    with pytest.raises(AiError) as info:
        c.generate_json("system", "prompt", questions.QuestionIntent)
    assert info.value.code == code and info.value.retryable is retryable


@pytest.mark.live_gemini
def test_live_gemini_end_to_end(client, kpi_data):
    """Real provider, real grounding. Opt-in: pytest --live-gemini (uses 3 requests of quota)."""
    settings = get_settings()
    if not settings.gemini_configured:
        pytest.skip("GEMINI_API_KEY / GEMINI_MODEL not set")
    summary = client.post("/api/v1/insights/generate", json={"type": "executive_summary", **JAN})
    assert summary.status_code == 201, summary.json()
    body = summary.json()
    assert body["status"] == "completed" and body["model"] == settings.gemini_model
    keys = {f["key"] for f in body["facts"]}
    assert all(f["evidence_key"] in keys for f in body["output"]["observed_facts"])
    answer = client.post("/api/v1/insights/query", json={"question": "Which category made the most revenue?", **JAN})
    assert answer.status_code == 201, answer.json()
    assert answer.json()["intent"]["intent"] in ("ranking", "kpi_overview", "change_drivers")
