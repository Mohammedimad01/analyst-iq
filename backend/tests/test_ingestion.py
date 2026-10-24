import io

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

import app.models as m
from app.core.config import get_settings
from app.services.ingestion import importer

HEADER = "order_id,order_date,store_id,channel,customer_id,product_sku,product_name,category,quantity,unit_price,discount_amount,unit_cost,status\n"
GOOD = (
    "A1,2025-03-01,S1,in_store,C1,P1,Widget,X,2,10.00,1.00,6.00,completed\n"
    "A1,2025-03-01,S1,in_store,C1,P2,Gadget,Y,1,20.00,,15.00,completed\n"
    "A2,2025-03-02,S2,Online,,P1,Widget,X,1,10.00,0,6.00,returned\n"
)


def upload(client, content: str | bytes, name="orders.csv"):
    data = content.encode() if isinstance(content, str) else content
    return client.post("/api/v1/data/imports", files={"file": (name, data)})


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_valid_csv_is_persisted(client, db):
    r = upload(client, HEADER + GOOD)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed", body
    assert (body["rows_received"], body["rows_accepted"], body["rows_rejected"], body["orders_accepted"]) == (3, 3, 0, 2)
    assert count(db, m.Order) == 2 and count(db, m.OrderItem) == 3
    assert count(db, m.Store) == 2 and count(db, m.Product) == 2 and count(db, m.Customer) == 1
    online = db.scalar(select(m.Order).where(m.Order.order_number == "A2"))
    assert online.channel == "online" and online.customer_id is None  # channel normalised, blank customer allowed


def test_invalid_line_rejects_its_whole_order_only(client, db):
    bad = (HEADER + GOOD
           + "B1,2025-03-03,S1,in_store,,P1,Widget,X,1,10.00,0,6.00,completed\n"
           + "B1,2025-03-03,S1,in_store,,P2,Gadget,Y,-1,20.00,0,15.00,completed\n")  # negative quantity
    body = upload(client, bad).json()
    assert body["status"] == "completed"
    assert body["orders_accepted"] == 2 and body["rows_rejected"] == 2
    assert any(e["row"] == 6 and e["column"] == "quantity" for e in body["errors"])
    assert any(e["row"] == 5 and "B1" in e["message"] for e in body["errors"])
    assert db.scalar(select(m.Order).where(m.Order.order_number == "B1")) is None


@pytest.mark.parametrize("row, column", [
    ("C1,03/04/2025,S1,in_store,,P1,W,X,1,10,0,6,completed", "order_date"),
    ("C1,2025-03-04,S1,in_store,,P1,W,X,1,$10,0,6,completed", "unit_price"),
    ("C1,2025-03-04,S1,in_store,,P1,W,X,1,10.001,0,6,completed", "unit_price"),
    ("C1,2025-03-04,S1,phone,,P1,W,X,1,10,0,6,completed", "channel"),
    ("C1,2025-03-04,S1,in_store,,P1,W,X,1,10,0,6,shipped", "status"),
    ("C1,2025-03-04,S1,in_store,,P1,W,X,1,10,11,6,completed", "discount_amount"),
    ("C1,2025-03-04,S1,in_store,,P1,W,X,1.5,10,0,6,completed", "quantity"),
    (",2025-03-04,S1,in_store,,P1,W,X,1,10,0,6,completed", "order_id"),
    ("C1,2025-03-04,,in_store,,P1,W,X,1,10,0,6,completed", "store_id"),
])
def test_row_level_validation(client, db, row, column):
    body = upload(client, HEADER + row + "\n").json()
    assert body["status"] == "rejected"
    assert body["errors"][0]["row"] == 2 and body["errors"][0]["column"] == column
    assert count(db, m.Order) == 0


def test_conflicting_order_fields_reject_order(client):
    rows = ("D1,2025-03-01,S1,in_store,,P1,W,X,1,10,0,6,completed\n"
            "D1,2025-03-01,S1,in_store,,P2,G,Y,1,20,0,15,cancelled\n")
    body = upload(client, HEADER + rows).json()
    assert body["status"] == "rejected" and body["rows_rejected"] == 2


def test_duplicate_line_numbers_reject_order(client):
    header = "order_id,line_number,order_date,store_id,channel,product_sku,product_name,category,quantity,unit_price,unit_cost,status\n"
    rows = ("E1,1,2025-03-01,S1,in_store,P1,W,X,1,10,6,completed\n"
            "E1,1,2025-03-01,S1,in_store,P2,G,Y,1,20,15,completed\n")
    assert upload(client, header + rows).json()["status"] == "rejected"


def test_reimport_never_overwrites_existing_orders(client, db):
    assert upload(client, HEADER + GOOD).json()["status"] == "completed"
    # Same orders with a changed price plus one new order: existing ones are rejected, new one accepted.
    changed = GOOD.replace("10.00,1.00", "99.00,1.00") + "F1,2025-03-05,S1,in_store,,P1,Widget,X,1,10,0,6,completed\n"
    body = upload(client, HEADER + changed).json()
    assert body["status"] == "completed" and body["orders_accepted"] == 1 and body["rows_rejected"] == 3
    assert "already imported" in body["errors"][0]["message"]
    prices = db.scalars(select(m.OrderItem.unit_price).join(m.Order).where(m.Order.order_number == "A1")).all()
    assert max(prices) == 20  # original facts untouched
    assert count(db, m.Order) == 3


def test_identical_file_is_rejected(client, db):
    assert upload(client, HEADER + GOOD).json()["status"] == "completed"
    body = upload(client, HEADER + GOOD).json()
    assert body["status"] == "rejected" and "already imported" in body["message"]
    assert count(db, m.Order) == 2


@pytest.mark.parametrize("content, message", [
    (HEADER, "no data rows"),
    ("order_id,order_date\nA,2025-01-01\n", "Missing required column(s)"),
    (b"\xff\xfe\x00bad", "not UTF-8"),
])
def test_file_level_rejections(client, db, content, message):
    body = upload(client, content).json()
    assert body["status"] == "rejected" and message in body["message"]
    assert count(db, m.Order) == 0


def test_upload_guards(client, db):
    assert upload(client, "x", name="orders.xlsm").status_code == 400
    assert upload(client, b"", name="orders.csv").status_code == 400
    settings = get_settings()
    original = settings.max_upload_mb
    settings.max_upload_mb = 0
    try:
        r = upload(client, HEADER + GOOD)
        assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    finally:
        settings.max_upload_mb = original
    assert count(db, m.DataImport) == 0


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_import_and_formulas_are_not_evaluated(client, db):
    header = HEADER.strip().split(",")
    good = ["X1", "2025-03-01", "S1", "in_store", "", "P1", "Widget", "X", 2, 10, 0, 6, "completed"]
    formula = ["X2", "2025-03-01", "S1", "in_store", "", "P1", "Widget", "X", "=1+1", 10, 0, 6, "completed"]
    body = upload(client, _xlsx([header, good, formula]), name="orders.xlsx").json()
    assert body["status"] == "completed" and body["orders_accepted"] == 1
    assert body["errors"][0]["column"] == "quantity"  # formula has no cached value, so it is never trusted


def test_corrupt_xlsx_is_rejected(client):
    body = upload(client, b"PK\x03\x04 not really a workbook", name="orders.xlsx").json()
    assert body["status"] == "rejected" and "could not be read" in body["message"]


def test_database_failure_writes_nothing(client, db, monkeypatch):
    real_write = importer._write_orders

    def write_then_fail(*args, **kwargs):
        real_write(*args, **kwargs)
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(importer, "_write_orders", write_then_fail)
    body = upload(client, HEADER + GOOD).json()
    assert body["status"] == "failed" and body["rows_accepted"] == 0
    assert count(db, m.Order) == 0 and count(db, m.OrderItem) == 0 and count(db, m.Product) == 0
    # The failed attempt does not block a retry of the same file.
    monkeypatch.setattr(importer, "_write_orders", real_write)
    assert upload(client, HEADER + GOOD).json()["status"] == "completed"


def test_import_history_endpoints(client):
    upload(client, HEADER + GOOD)
    upload(client, HEADER)
    listing = client.get("/api/v1/data/imports?limit=1").json()
    assert listing["total"] == 2 and len(listing["items"]) == 1 and listing["items"][0]["status"] == "rejected"
    first_id = client.get("/api/v1/data/imports").json()["items"][-1]["id"]
    assert client.get(f"/api/v1/data/imports/{first_id}").json()["status"] == "completed"
    missing = client.get("/api/v1/data/imports/9999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_interrupted_imports_are_marked_failed(client, db, org_id):
    from datetime import timedelta
    stale = m.DataImport(organization_id=org_id, filename="x.csv", file_sha256="0" * 64, status="processing",
                         errors=[], started_at=m.utcnow() - timedelta(hours=2))
    db.add(stale)
    db.commit()
    assert upload(client, HEADER + GOOD).json()["status"] == "completed"
    db.refresh(stale)
    assert stale.status == "failed" and "Interrupted" in stale.message
