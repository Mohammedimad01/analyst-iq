import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (analytics, anomalies, automation, dashboard, health, imports, insights, reports,
                            workspace)
from app.core.config import get_settings
from app.core.errors import register_error_handlers

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("analyst_iq.http")

docs = settings.expose_api_docs if settings.expose_api_docs is not None else settings.environment != "production"
app = FastAPI(
    title="Analyst IQ API",
    version=health.VERSION,
    description="Retail analytics: deterministic KPIs, data imports, anomaly detection, grounded AI insights, "
                "reports and authenticated automation endpoints.",
    docs_url="/docs" if docs else None, redoc_url=None, openapi_url="/openapi.json" if docs else None,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "Authorization"])
register_error_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    # Path only — query strings can carry filter values and are not needed to diagnose latency.
    log.info("%s %s -> %s in %.0f ms", request.method, request.url.path, response.status_code,
             (time.perf_counter() - started) * 1000)
    # JSON API: nothing here should be framed, sniffed or leak a referrer.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


for router in (health.router, workspace.router, dashboard.router, analytics.router, imports.router,
               anomalies.router, insights.router, reports.router, automation.router):
    app.include_router(router, prefix="/api/v1")

if settings.database_backend == "sqlite":
    log.warning("DATABASE_URL is not set: using local SQLite fallback (demo/development only).")
