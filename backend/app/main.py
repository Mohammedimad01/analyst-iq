import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, anomalies, dashboard, health, imports, insights
from app.core.config import get_settings
from app.core.errors import register_error_handlers

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("analyst_iq.http")

app = FastAPI(
    title="Analyst IQ API",
    version=health.VERSION,
    description="Retail analytics: deterministic KPIs, data imports, and (later) AI-written insights.",
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
    return response


for router in (health.router, dashboard.router, analytics.router, imports.router, anomalies.router,
               insights.router):
    app.include_router(router, prefix="/api/v1")

if settings.database_backend == "sqlite":
    log.warning("DATABASE_URL is not set: using local SQLite fallback (demo/development only).")
