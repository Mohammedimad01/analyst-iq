"""File reading and row validation. Pure functions: no database access, so the rules are easy to unit-test.

Rules are documented in docs/DATA_MODEL.md ("Import rules").
"""

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath

import pandas as pd

from app.models import CHANNELS, ORDER_STATUSES

ALLOWED_EXTENSIONS = (".csv", ".xlsx")
REQUIRED_COLUMNS = ("order_id", "order_date", "store_id", "channel", "product_sku", "product_name", "category",
                    "quantity", "unit_price", "unit_cost", "status")
OPTIONAL_COLUMNS = ("line_number", "discount_amount", "customer_id", "customer_segment", "customer_region",
                    "store_name", "store_region")
MAX_LENGTHS = {"order_id": 64, "store_id": 50, "product_sku": 64, "product_name": 200, "category": 100,
               "customer_id": 50, "customer_segment": 50, "customer_region": 100, "store_name": 200,
               "store_region": 100}
PREFERRED_SHEETS = ("orders", "sales", "data")
MAX_MONEY = Decimal("9999999999.99")
CENT = Decimal("0.01")


class FileContentError(Exception):
    """The file as a whole cannot be imported (unreadable, empty, missing columns)."""


@dataclass
class LineDraft:
    row: int
    line_number: int | None
    product_sku: str
    product_name: str
    category: str
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    unit_cost: Decimal


@dataclass
class OrderDraft:
    order_number: str
    order_date: date
    store_code: str
    store_name: str | None
    store_region: str | None
    channel: str
    status: str
    customer_code: str | None
    customer_segment: str | None
    customer_region: str | None
    lines: list[LineDraft] = field(default_factory=list)


@dataclass
class ParseResult:
    orders: dict[str, OrderDraft]
    errors: list[dict]
    rows_received: int
    rows_rejected: int


def read_table(filename: str, content: bytes) -> pd.DataFrame:
    """Read every cell as text. Excel formulas are never evaluated: openpyxl returns cached values only."""
    ext = PurePath(filename).suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig")
        elif ext == ".xlsx":
            sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str, keep_default_na=False,
                                   engine="openpyxl")
            if not sheets:
                raise FileContentError("The workbook contains no sheets.")
            by_name = {name.strip().lower(): name for name in sheets}
            chosen = next((by_name[n] for n in PREFERRED_SHEETS if n in by_name), next(iter(sheets)))
            df = sheets[chosen]
        else:
            raise FileContentError(f"Unsupported file type '{ext}'. Upload a .csv or .xlsx file.")
    except FileContentError:
        raise
    except pd.errors.EmptyDataError:
        raise FileContentError("The file is empty.")
    except UnicodeDecodeError:
        raise FileContentError("The CSV is not UTF-8 encoded. Re-save it as UTF-8 and try again.")
    except Exception as exc:  # malformed CSV, corrupt zip, wrong format behind the extension
        raise FileContentError(f"The file could not be read as {ext}: {type(exc).__name__}.")

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if df.empty:
        raise FileContentError("The file has a header row but no data rows.")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise FileContentError(f"Missing required column(s): {', '.join(missing)}.")
    return df


def _text(raw: str, column: str, errors: list[str], required: bool) -> str | None:
    value = (raw or "").strip()
    if not value:
        if required:
            errors.append(f"{column}: value is required")
        return None
    limit = MAX_LENGTHS.get(column)
    if limit and len(value) > limit:
        errors.append(f"{column}: longer than {limit} characters")
        return None
    return value


def _money(raw: str, column: str, errors: list[str], default: Decimal | None = None) -> Decimal | None:
    value = (raw or "").strip()
    if not value and default is not None:
        return default
    try:
        amount = Decimal(value)
    except InvalidOperation:
        errors.append(f"{column}: '{value}' is not a number (use plain digits, e.g. 1234.50)")
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_MONEY:
        errors.append(f"{column}: must be between 0 and {MAX_MONEY}")
        return None
    if amount != amount.quantize(CENT):
        errors.append(f"{column}: more than 2 decimal places")
        return None
    return amount.quantize(CENT)


def _positive_int(raw: str, column: str, errors: list[str], required: bool = True) -> int | None:
    value = (raw or "").strip()
    if not value:
        if required:
            errors.append(f"{column}: value is required")
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        errors.append(f"{column}: '{value}' is not a whole number")
        return None
    if not number.is_finite() or number != number.to_integral_value() or number <= 0:
        hint = "; record returns with status=returned" if column == "quantity" else ""
        errors.append(f"{column}: must be a positive whole number{hint}")
        return None
    return int(number)


def _date(raw: str, errors: list[str]) -> date | None:
    value = (raw or "").strip()
    try:
        # ISO only (YYYY-MM-DD, optionally with a time from Excel). Formats like 03/04/2025 are ambiguous.
        return datetime.fromisoformat(value).date()
    except ValueError:
        errors.append(f"order_date: '{value}' is not a valid date in YYYY-MM-DD format")
        return None


def _choice(raw: str, column: str, allowed: tuple[str, ...], errors: list[str]) -> str | None:
    value = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value not in allowed:
        errors.append(f"{column}: '{raw}' must be one of {', '.join(allowed)}")
        return None
    return value


ORDER_FIELDS = ("order_date", "store_code", "channel", "status", "customer_code")


def parse_rows(df: pd.DataFrame, max_errors: int = 200) -> ParseResult:
    """Validate rows and group them into orders. An order with any bad line is rejected as a whole."""
    row_errors: dict[int, list[str]] = {}
    orders: dict[str, OrderDraft] = {}
    order_rows: dict[str, list[int]] = {}
    bad_orders: dict[str, str] = {}
    get = lambda record, col: record.get(col, "")  # noqa: E731

    for index, record in enumerate(df.to_dict("records")):
        row = index + 2  # spreadsheet row number: header is row 1
        errs: list[str] = []
        order_number = _text(get(record, "order_id"), "order_id", errs, required=True)
        order_date = _date(get(record, "order_date"), errs)
        store_code = _text(get(record, "store_id"), "store_id", errs, required=True)
        channel = _choice(get(record, "channel"), "channel", CHANNELS, errs)
        status = _choice(get(record, "status"), "status", ORDER_STATUSES, errs)
        sku = _text(get(record, "product_sku"), "product_sku", errs, required=True)
        name = _text(get(record, "product_name"), "product_name", errs, required=True)
        category = _text(get(record, "category"), "category", errs, required=True)
        quantity = _positive_int(get(record, "quantity"), "quantity", errs)
        line_number = _positive_int(get(record, "line_number"), "line_number", errs, required=False)
        unit_price = _money(get(record, "unit_price"), "unit_price", errs)
        unit_cost = _money(get(record, "unit_cost"), "unit_cost", errs)
        discount = _money(get(record, "discount_amount"), "discount_amount", errs, default=Decimal("0.00"))
        if discount is not None and unit_price is not None and quantity is not None and discount > quantity * unit_price:
            errs.append("discount_amount: larger than quantity × unit_price")
        customer_code = _text(get(record, "customer_id"), "customer_id", errs, required=False)

        if order_number is None:
            row_errors[row] = errs
            continue
        order_rows.setdefault(order_number, []).append(row)
        if errs:
            row_errors[row] = errs
            bad_orders.setdefault(order_number, f"row {row} is invalid")
            continue

        draft = OrderDraft(
            order_number=order_number, order_date=order_date, store_code=store_code,
            store_name=_text(get(record, "store_name"), "store_name", [], False),
            store_region=_text(get(record, "store_region"), "store_region", [], False),
            channel=channel, status=status, customer_code=customer_code,
            customer_segment=_text(get(record, "customer_segment"), "customer_segment", [], False),
            customer_region=_text(get(record, "customer_region"), "customer_region", [], False),
        )
        existing = orders.get(order_number)
        if existing is None:
            orders[order_number] = existing = draft
        elif any(getattr(existing, f) != getattr(draft, f) for f in ORDER_FIELDS):
            row_errors.setdefault(row, []).append("order-level fields (date, store, channel, status, customer) "
                                                  "differ from earlier lines of the same order")
            bad_orders.setdefault(order_number, f"row {row} conflicts with other lines")
        existing.lines.append(LineDraft(row, line_number, sku, name, category, quantity, unit_price, discount,
                                        unit_cost))

    # Assign or check line numbers per order.
    for order_number, draft in orders.items():
        if order_number in bad_orders:
            continue
        if all(line.line_number is None for line in draft.lines):
            for i, line in enumerate(draft.lines, start=1):
                line.line_number = i
        seen: set[int | None] = set()
        for line in draft.lines:
            if line.line_number is None or line.line_number in seen:
                row_errors.setdefault(line.row, []).append("line_number: missing or duplicated within the order")
                bad_orders.setdefault(order_number, f"row {line.row} has a duplicate line_number")
            seen.add(line.line_number)

    return _finish(orders, order_rows, bad_orders, row_errors, len(df), max_errors)


def reject_orders(result: ParseResult, reasons: dict[str, str], max_errors: int = 200) -> ParseResult:
    """Remove whole orders after parsing (e.g. already imported) and record why."""
    for order_number, reason in reasons.items():
        draft = result.orders.pop(order_number, None)
        if draft is None:
            continue
        result.rows_rejected += len(draft.lines)
        for line in draft.lines:
            if len(result.errors) < max_errors:
                result.errors.append({"row": line.row, "column": "order_id", "message": reason})
    return result


def _finish(orders, order_rows, bad_orders, row_errors, rows_received, max_errors) -> ParseResult:
    errors: list[dict] = []
    rejected_rows: set[int] = set(row_errors)
    for order_number, reason in bad_orders.items():
        orders.pop(order_number, None)
        for row in order_rows[order_number]:
            rejected_rows.add(row)
            if row not in row_errors:
                row_errors[row] = [f"order {order_number} rejected because {reason}"]
    for row in sorted(row_errors):
        for message in row_errors[row]:
            column = message.split(":", 1)[0] if ":" in message else None
            if len(errors) < max_errors:
                errors.append({"row": row, "column": column, "message": message})
    return ParseResult(orders=orders, errors=errors, rows_received=rows_received, rows_rejected=len(rejected_rows))
