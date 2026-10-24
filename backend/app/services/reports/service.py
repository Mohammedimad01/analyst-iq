import re
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Organization, Report, utcnow
from app.services.analytics.metrics import Filters
from app.services.organization import data_mix
from app.services.reports.builder import REPORT_TITLES, build_report, has_sales
from app.services.reports.render import to_csv, to_pdf

MAX_REPORT_BYTES = 5 * 1024 * 1024
CONTENT_TYPES = {"pdf": "application/pdf", "csv": "text/csv; charset=utf-8"}


def generate_report(db: Session, org_id: int, report_type: str, file_format: str, f: Filters, params: dict,
                    requested_by: str = "ui") -> Report:
    if not has_sales(db, org_id, f):
        raise AppError(422, "There are no completed sales in the selected period and filters, so there is nothing "
                            "to report. Widen the date range or clear a filter.", code="empty_report")
    started = time.perf_counter()
    organization = db.scalar(select(Organization.name).where(Organization.id == org_id)) or "Analyst IQ"
    kind, _, _ = data_mix(db, org_id)
    synthetic = kind in ("synthetic", "mixed")
    report = build_report(db, org_id, report_type, f, organization, synthetic)
    now = utcnow()
    content = to_pdf(report, now) if file_format == "pdf" else to_csv(report)
    if len(content) > MAX_REPORT_BYTES:
        raise AppError(413, "The report is too large. Narrow the date range or filters.", code="payload_too_large")
    slug = re.sub(r"[^a-z0-9]+", "-", REPORT_TITLES[report_type].lower()).strip("-")
    record = Report(organization_id=org_id, report_type=report_type, title=report.title, file_format=file_format,
                    filename=f"analyst-iq-{slug}-{f.start_date.isoformat()}-to-{f.end_date.isoformat()}.{file_format}",
                    params=params, content=content, size_bytes=len(content), contains_synthetic=synthetic,
                    requested_by=requested_by, created_at=now,
                    duration_ms=int((time.perf_counter() - started) * 1000))
    db.add(record)
    db.commit()
    return record
