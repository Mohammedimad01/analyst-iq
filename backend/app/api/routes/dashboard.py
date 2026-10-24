from fastapi import APIRouter

from app.api.deps import AnalyticsFilters, DbSession, OrgId
from app.schemas import FilterOptions, Overview, Period
from app.services.analytics import metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
TOP_PRODUCTS = 10


def period(f: metrics.Filters) -> Period:
    return Period(start_date=f.start_date, end_date=f.end_date, days=f.days)


@router.get("/filters", response_model=FilterOptions)
def filter_options(db: DbSession, org_id: OrgId):
    return metrics.filter_options(db, org_id)


@router.get("/overview", response_model=Overview)
def overview(db: DbSession, org_id: OrgId, f: AnalyticsFilters):
    return {
        "period": period(f),
        "comparison_period": period(f.previous_period()),
        "kpis": metrics.kpis_with_comparison(db, org_id, f),
        "trend": metrics.trend(db, org_id, f),
        "by_category": metrics.breakdown(db, org_id, f, "category"),
        "by_store": metrics.breakdown(db, org_id, f, "store"),
        "by_channel": metrics.breakdown(db, org_id, f, "channel"),
        "top_products": metrics.breakdown(db, org_id, f, "product")[:TOP_PRODUCTS],
    }
