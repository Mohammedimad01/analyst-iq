"""Evidence facts and the number check that keeps model output tied to them.

Every number the model writes must match a verified fact value, allowing only for the rounding implied by how the
number is written ("$325K" may stand for 324,648.99; "12.9%" may not stand for 12.33).
"""

import re
from datetime import date
from decimal import Decimal

MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_PATTERNS = re.compile("|".join([
    r"\b\d{4}-\d{2}-\d{2}\b",
    MONTH + r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?",
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+" + MONTH + r"(?:,?\s+\d{4})?",
    MONTH + r"\s+\d{4}",
    r"\b(?:19|20)\d{2}\b",
    r"\bQ[1-4]\b",
]), re.IGNORECASE)
NUMBER = re.compile(
    r"(?<![\w.\-−])(?P<sign>[-−+])?(?P<cur>[$€£])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suf>\s?%|\s?pp\b|\s?percentage points?\b|[kKmM]\b|\s?bn\b)?(?![\w])")
MULTIPLIER = {"k": 1e3, "m": 1e6, "bn": 1e9}


def fact(key: str, label: str, value, unit: str = "text") -> dict:
    """unit: currency | percent | pp | count | number | text."""
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, date):
        value = value.isoformat()
    if value is None:
        display = "not available"
    elif unit == "currency":
        display = f"${value:,.2f}"
    elif unit == "percent":
        display = f"{value:.1f}%"
    elif unit == "pp":
        display = f"{value:+.1f} percentage points"
    elif unit == "count":
        display = f"{value:,.0f}"
    elif unit == "number":
        display = f"{value:,.2f}"
    else:
        display = str(value)
    return {"key": key, "label": label, "value": value, "unit": unit, "display": display}


def numbers_in(text: str) -> list[tuple[float, float]]:
    """(value, tolerance) for each number written in the text, ignoring dates, years and small bare counts."""
    cleaned = DATE_PATTERNS.sub(" ", text)
    found = []
    for m in NUMBER.finditer(cleaned):
        raw = m.group("num").replace(",", "")
        suffix = (m.group("suf") or "").strip().lower()
        multiplier = MULTIPLIER.get(suffix, 1.0)
        value = float(raw) * multiplier
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not m.group("cur") and not suffix and decimals == 0 and value <= 10:
            continue  # "top 3 stores", "2 channels": too ambiguous to verify, too small to mislead
        tolerance = 0.5 * 10 ** -decimals * multiplier
        if not m.group("cur") and not suffix and decimals == 0 and "," not in m.group("num"):
            tolerance = max(tolerance, 0.5)
        found.append((value, tolerance))
    return found


def allowed_values(facts: list[dict], extra: list[float] = ()) -> list[float]:
    values = [abs(float(f["value"])) for f in facts if isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool)]
    return values + [abs(v) for v in extra]


def unverified_numbers(text: str, allowed: list[float]) -> list[float]:
    bad = []
    for value, tolerance in numbers_in(text):
        if not any(abs(value - a) <= tolerance + 1e-9 or (a and abs(value - a) / a <= 0.001) for a in allowed):
            bad.append(value)
    return bad
