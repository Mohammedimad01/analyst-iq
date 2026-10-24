from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import AnalyticsFilters, DbSession, OrgId
from app.api.routes.dashboard import period
from app.schemas import BreakdownPage, CustomerAnalytics, SalesAnalytics
from app.services.analytics import metrics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/sales", response_model=SalesAnalytics)
def sales(db: DbSession, org_id: OrgId, f: AnalyticsFilters,
          grain: Literal["day", "week", "month"] | None = None):
    return {
        "period": period(f),
        "trend": metrics.trend(db, org_id, f, grain),
        "by_category": metrics.breakdown(db, org_id, f, "category"),
        "by_channel": metrics.breakdown(db, org_id, f, "channel"),
    }


@router.get("/breakdown/{dimension}", response_model=BreakdownPage)
def breakdown(
    dimension: Literal["product", "category", "store", "channel"],
    db: DbSession, org_id: OrgId, f: AnalyticsFilters,
    sort: Literal["net_revenue", "gross_profit", "gross_margin_pct", "units", "orders"] = "net_revenue",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # shortcut: groups are sorted/paginated in Python; fine for thousands of SKUs, move to SQL beyond that.
    rows = metrics.sort_rows(metrics.breakdown(db, org_id, f, dimension), sort, order == "desc")
    return {"dimension": dimension, "period": period(f), "total": len(rows), "limit": limit, "offset": offset,
            "concentration": metrics.top_share([r["net_revenue"] for r in rows]),
            "items": rows[offset:offset + limit]}


@router.get("/customers", response_model=CustomerAnalytics)
def customers(db: DbSession, org_id: OrgId, f: AnalyticsFilters,
              grain: Literal["day", "week", "month"] | None = None):
    return {"period": period(f), **metrics.customer_analytics(db, org_id, f, grain)}
