"""PDF (fpdf2, pure Python) and CSV rendering of a builder.Report."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from fpdf import FPDF

from app.services.reports.builder import Report, Table, cell_value

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# Core PDF fonts only cover Latin-1; map the few typographic characters our labels use.
LATIN1 = str.maketrans({
    "–": "-", "—": "-", "−": "-", "÷": "/", "×": "x", "Σ": "Sum of ", "≥": ">=", "≤": "<=",
    "’": "'", "“": '"', "”": '"', "…": "...",
})


def safe_text(value: str) -> str:
    """Neutralise spreadsheet formulas in user-controlled text (CSV injection): prefix with an apostrophe."""
    return "'" + value if value.startswith(FORMULA_PREFIXES) else value


def fmt(value, kind: str) -> str:
    if isinstance(value, tuple):
        value, kind = value
    if value is None:
        return "n/a"
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if kind == "currency":
        return f"${float(value):,.2f}"
    if kind == "percent":
        return f"{float(value):.1f}%"
    if kind == "pp":
        return f"{float(value):+.1f} pp"
    if kind == "count":
        return f"{float(value):,.0f}" if float(value) == int(float(value)) else f"{float(value):,.2f}"
    if kind == "number":
        return f"{float(value):,.2f}"
    return str(value)


# ---------------------------------------------------------------- CSV

def raw(value) -> object:
    v = cell_value(value)
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    if isinstance(v, str):
        return safe_text(v)
    return v


def table_csv(table: Table, writer) -> None:
    writer.writerow([safe_text(h) for h, _ in table.columns])
    for row in table.rows:
        writer.writerow([raw(v) for v in row])


def to_csv(report: Report) -> bytes:
    """Stacked tables: a title line, header and rows per section. Numbers are raw (unformatted) for analysis."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([safe_text(report.title)])
    for k, v in report.meta:
        w.writerow([k, safe_text(v)])
    for note in report.notes:
        w.writerow(["Note", safe_text(note)])
    for table in report.tables:
        w.writerow([])
        w.writerow([safe_text(table.title)])
        table_csv(table, w)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly


def single_table_csv(table: Table) -> bytes:
    buf = io.StringIO()
    table_csv(table, csv.writer(buf))
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------- PDF

class _Pdf(FPDF):
    footer_text = ""

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", size=7)
        self.set_text_color(120)
        self.cell(0, 6, self.footer_text, align="L")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")


def latin1(text: str) -> str:
    return text.translate(LATIN1).encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: Report, generated_at: datetime) -> bytes:
    pdf = _Pdf(orientation="P", unit="mm", format="A4")
    pdf.footer_text = latin1(f"Analyst IQ - generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.multi_cell(0, 8, latin1(report.title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=9)
    for k, v in report.meta:
        pdf.multi_cell(0, 5, latin1(f"{k}: {v}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    for i, note in enumerate(report.notes):
        synthetic = i == 0 and note.startswith("SYNTHETIC")
        pdf.set_font("helvetica", "B" if synthetic else "", 8)
        pdf.set_text_color(160, 90, 0) if synthetic else pdf.set_text_color(90)
        pdf.multi_cell(0, 4, latin1(note), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
    for table in report.tables:
        pdf.ln(4)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, latin1(table.title), new_x="LMARGIN", new_y="NEXT")
        if not table.rows:
            pdf.set_font("helvetica", "I", 8)
            pdf.cell(0, 5, "No data for this selection.", new_x="LMARGIN", new_y="NEXT")
            continue
        pdf.set_font("helvetica", size=7.5)
        text_cols = [kind == "text" for _, kind in table.columns]
        widths = [3 if t else 2 for t in text_cols]
        if table.columns[-1][0] == "Definition":
            widths = [1, 3]
        align = tuple("LEFT" if t else "RIGHT" for t in text_cols)
        with pdf.table(col_widths=widths, text_align=align, line_height=4.2, first_row_as_headings=True,
                       borders_layout="HORIZONTAL_LINES") as t:
            header = t.row()
            for name, _ in table.columns:
                header.cell(latin1(name))
            for row in table.rows:
                r = t.row()
                for value, (_, kind) in zip(row, table.columns):
                    r.cell(latin1(fmt(value, kind)))
        if table.note:
            pdf.set_font("helvetica", "I", 7)
            pdf.set_text_color(90)
            pdf.multi_cell(0, 4, latin1(table.note), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0)
    return bytes(pdf.output())
