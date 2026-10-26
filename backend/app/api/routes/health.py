import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings
from app.schemas import Health

router = APIRouter(tags=["system"])
log = logging.getLogger("analyst_iq.health")
VERSION = "0.1.0"


@router.api_route("/ping", methods=["GET", "HEAD"])
def ping() -> dict:
    """Keep-awake target for an uptime pinger. No database access, so pings never wake or bill the database."""
    return {"status": "ok"}


@router.get("/health", response_model=Health)
def health(db: DbSession) -> Health:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        log.warning("health check: database unavailable (%s)", type(exc).__name__)
        database = "unavailable"
    return Health(status="ok" if database == "ok" else "degraded", database=database,
                  database_backend=settings.database_backend, gemini_configured=settings.gemini_configured,
                  version=VERSION)
