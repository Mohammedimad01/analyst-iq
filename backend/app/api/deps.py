from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.services.analytics.metrics import Filters
from app.services.organization import get_demo_org_id

MAX_RANGE_DAYS = 1096

DbSession = Annotated[Session, Depends(get_db)]


def get_org_id(db: DbSession) -> int:
    # Single demo organisation until authentication exists (docs/ARCHITECTURE.md, "Security posture").
    return get_demo_org_id(db)


OrgId = Annotated[int, Depends(get_org_id)]


def get_filters(
    start_date: Annotated[date, Query(description="Inclusive start (order business date)")],
    end_date: Annotated[date, Query(description="Inclusive end")],
    store: Annotated[list[str], Query(max_length=50, description="Store codes")] = [],
    category: Annotated[list[str], Query(max_length=50)] = [],
    channel: Annotated[list[Literal["in_store", "online", "marketplace"]], Query()] = [],
) -> Filters:
    if end_date < start_date:
        raise AppError(422, "end_date must be on or after start_date")
    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise AppError(422, f"Date range is limited to {MAX_RANGE_DAYS} days")
    return Filters(start_date, end_date, tuple(store), tuple(category), tuple(channel))


AnalyticsFilters = Annotated[Filters, Depends(get_filters)]
