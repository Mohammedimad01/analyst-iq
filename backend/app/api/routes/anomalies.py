import time
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession, OrgId
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.models import AnalysisRun
from app.schemas import AnomalyRun, AnomalyRunList
from app.services.anomaly_detection.detector import DetectionConfig, detect

router = APIRouter(prefix="/anomalies", tags=["anomalies"])
ANALYSIS_TYPE = "anomaly_detection"
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


class DetectRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    config: DetectionConfig = DetectionConfig()


def _period(r: dict | None) -> dict | None:
    if not r:
        return None
    days = (date.fromisoformat(r["end_date"]) - date.fromisoformat(r["start_date"])).days + 1
    return {**r, "days": days}


def to_response(run: AnalysisRun, min_severity: str = "low") -> dict:
    result = run.result
    anomalies = [a for a in result.get("anomalies", []) if SEVERITY_RANK[a["severity"]] <= SEVERITY_RANK[min_severity]]
    return {"id": run.id, "created_at": run.created_at, "duration_ms": run.duration_ms,
            "data_range": _period(result.get("data_range")), "evaluated_range": _period(result.get("evaluated_range")),
            "counts": result.get("counts", {}), "anomalies": anomalies}


def latest_run(db, org_id: int) -> AnalysisRun | None:
    return db.scalar(select(AnalysisRun).where(AnalysisRun.organization_id == org_id,
                                               AnalysisRun.analysis_type == ANALYSIS_TYPE)
                     .order_by(AnalysisRun.id.desc()).limit(1))


@router.post("/detect", response_model=AnomalyRun, status_code=201,
             dependencies=[Depends(rate_limit("detection", 10))])
def run_detection(body: DetectRequest, db: DbSession, org_id: OrgId):
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise AppError(422, "end_date must be on or after start_date")
    started = time.perf_counter()
    result = detect(db, org_id, body.config, body.start_date, body.end_date)
    run = AnalysisRun(organization_id=org_id, analysis_type=ANALYSIS_TYPE, params=body.model_dump(mode="json"),
                      result=result, duration_ms=int((time.perf_counter() - started) * 1000))
    db.add(run)
    db.commit()
    return to_response(run)


@router.get("/latest", response_model=AnomalyRun)
def get_latest(db: DbSession, org_id: OrgId,
               min_severity: Annotated[Literal["high", "medium", "low"], Query()] = "low"):
    run = latest_run(db, org_id)
    if run is None:
        raise AppError(404, "Anomaly detection has not been run yet.")
    return to_response(run, min_severity)


@router.get("/runs", response_model=AnomalyRunList)
def list_runs(db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    scope = (AnalysisRun.organization_id == org_id, AnalysisRun.analysis_type == ANALYSIS_TYPE)
    total = db.scalar(select(func.count()).select_from(AnalysisRun).where(*scope))
    runs = db.scalars(select(AnalysisRun).where(*scope).order_by(AnalysisRun.id.desc()).limit(limit))
    return {"total": total, "items": [{"id": r.id, "created_at": r.created_at, "counts": r.result.get("counts", {}),
                                       "evaluated_range": _period(r.result.get("evaluated_range"))} for r in runs]}
