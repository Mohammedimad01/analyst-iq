"""Import orchestration: record the import, validate, and write accepted orders in one transaction."""

import hashlib
import logging
import time
from collections.abc import Iterable, Iterator
from datetime import timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.models import Customer, DataImport, Order, OrderItem, Product, Store, utcnow
from app.services.ingestion.parsing import FileContentError, ParseResult, parse_rows, read_table, reject_orders

log = logging.getLogger("analyst_iq.ingestion")
CHUNK = 900  # keeps IN (...) lists under SQLite's bound-parameter limit


def _chunks(items: list, size: int = CHUNK) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def run_import(db: Session, org_id: int, filename: str, content: bytes, max_rows: int,
               source: str = "upload") -> DataImport:
    started = time.perf_counter()
    # A process killed mid-import leaves its record at "processing"; nothing was written (the data transaction
    # rolled back), so say so instead of showing it as running forever.
    db.execute(update(DataImport).where(
        DataImport.organization_id == org_id, DataImport.status == "processing",
        DataImport.started_at < utcnow() - timedelta(hours=1),
    ).values(status="failed", finished_at=utcnow(),
             message="Interrupted before completion (the process stopped). Nothing was written; import again."))
    record = DataImport(organization_id=org_id, filename=filename[:255], source=source,
                        file_sha256=hashlib.sha256(content).hexdigest(), status="processing", errors=[])
    db.add(record)
    db.commit()  # the attempt is recorded even if everything below fails

    def finish(status: str, message: str, result: ParseResult | None = None) -> DataImport:
        record.status = status
        record.message = message
        if result is not None:
            record.rows_received = result.rows_received
            record.rows_rejected = result.rows_rejected
            record.errors = result.errors
        record.finished_at = utcnow()
        record.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        log.info("import %s %s: %s", record.id, status, message)
        return record

    duplicate_of = db.scalar(select(DataImport.id).where(
        DataImport.organization_id == org_id, DataImport.file_sha256 == record.file_sha256,
        DataImport.status == "completed", DataImport.id != record.id))
    if duplicate_of is not None:
        return finish("rejected", f"This exact file was already imported (import #{duplicate_of}). Nothing was written.")

    try:
        df = read_table(filename, content)
    except FileContentError as exc:
        return finish("rejected", str(exc))
    if len(df) > max_rows:
        return finish("rejected", f"The file has {len(df):,} rows; the limit is {max_rows:,}. Split it and retry.")

    result = parse_rows(df)
    existing = _existing_order_numbers(db, org_id, list(result.orders))
    reject_orders(result, {n: f"order {n} was already imported; existing orders are never overwritten"
                           for n in existing})
    if not result.orders:
        return finish("rejected", "No valid orders found. See the row errors for details.", result)

    try:
        lines_written = _write_orders(db, org_id, record.id, result)
        record.rows_accepted = lines_written
        record.orders_accepted = len(result.orders)
        summary = f"Imported {len(result.orders):,} orders ({lines_written:,} lines)."
        if result.rows_rejected:
            summary += f" {result.rows_rejected:,} rows rejected."
        return finish("completed", summary, result)  # commits data and status together
    except Exception:
        db.rollback()
        log.exception("import %s failed while writing", record.id)
        record = db.get(DataImport, record.id)
        record.rows_accepted = 0
        record.orders_accepted = 0
        return finish("failed", "The database rejected the import, so nothing was written. Try again; if it "
                                "keeps failing, check the server logs.", result)


def _existing_order_numbers(db: Session, org_id: int, numbers: list[str]) -> set[str]:
    found: set[str] = set()
    for chunk in _chunks(numbers):
        found.update(db.scalars(select(Order.order_number).where(
            Order.organization_id == org_id, Order.order_number.in_(chunk))))
    return found


def _ensure(db: Session, model, org_id: int, code_attr: str, wanted: dict[str, dict]) -> dict[str, int]:
    """Map code -> id, inserting codes not seen before. Existing rows are never modified."""
    code_col = getattr(model, code_attr)
    ids: dict[str, int] = {}
    for chunk in _chunks(list(wanted)):
        ids.update(db.execute(select(code_col, model.id).where(
            model.organization_id == org_id, code_col.in_(chunk))).all())
    missing = [{"organization_id": org_id, code_attr: code, **attrs} for code, attrs in wanted.items()
               if code not in ids]
    table = model.__table__
    for chunk in _chunks(missing):
        ids.update(_bulk(db, insert(table).returning(table.c[code_attr], table.c.id), chunk).all())
    return ids


def _bulk(db: Session, stmt, rows: list[dict]):
    # Core statement on the session's connection (same transaction). The ORM bulk path splits a batch whenever
    # NULL-ness changes between rows (e.g. walk-in orders without customer_id): ~5 rows per round trip, which made
    # a 35k-line import take over 10 minutes against a remote database instead of under a minute.
    return db.connection().execute(stmt, rows)


def _first_wins(pairs: Iterable[tuple[str, dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for code, attrs in pairs:
        out.setdefault(code, attrs)
    return out


def _write_orders(db: Session, org_id: int, import_id: int, result: ParseResult) -> int:
    drafts = list(result.orders.values())
    store_ids = _ensure(db, Store, org_id, "store_code", _first_wins(
        (d.store_code, {"name": d.store_name or d.store_code, "region": d.store_region}) for d in drafts))
    customer_ids = _ensure(db, Customer, org_id, "customer_code", _first_wins(
        (d.customer_code, {"segment": d.customer_segment, "region": d.customer_region})
        for d in drafts if d.customer_code))
    product_ids = _ensure(db, Product, org_id, "sku", _first_wins(
        (line.product_sku, {"name": line.product_name, "category": line.category})
        for d in drafts for line in d.lines))

    order_ids: dict[str, int] = {}
    order_rows = [{"organization_id": org_id, "order_number": d.order_number, "order_date": d.order_date,
                   "store_id": store_ids[d.store_code], "customer_id": customer_ids.get(d.customer_code),
                   "channel": d.channel, "status": d.status, "import_id": import_id, "created_at": utcnow()}
                  for d in drafts]
    orders = Order.__table__
    for chunk in _chunks(order_rows):
        order_ids.update(_bulk(db, insert(orders).returning(orders.c.order_number, orders.c.id), chunk).all())

    item_rows = [{"order_id": order_ids[d.order_number], "line_number": line.line_number,
                  "product_id": product_ids[line.product_sku], "quantity": line.quantity,
                  "unit_price": line.unit_price, "discount_amount": line.discount_amount,
                  "unit_cost": line.unit_cost}
                 for d in drafts for line in d.lines]
    for chunk in _chunks(item_rows, 5000):
        _bulk(db, insert(OrderItem.__table__), chunk)
    return len(item_rows)
