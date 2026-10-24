from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession, OrgId
from app.core.config import get_settings
from app.models import DataImport, Organization
from app.schemas import Workspace
from app.services.organization import data_mix

router = APIRouter(tags=["system"])


@router.get("/workspace", response_model=Workspace)
def workspace(db: DbSession, org_id: OrgId):
    """What the UI needs to label itself honestly: whose data, what kind, and which optional features are on."""
    settings = get_settings()
    kind, synthetic, imported = data_mix(db, org_id)
    last = db.scalar(select(DataImport).where(DataImport.organization_id == org_id)
                     .order_by(DataImport.id.desc()).limit(1))
    return {
        "organization_name": db.scalar(select(Organization.name).where(Organization.id == org_id)),
        "data_kind": kind, "synthetic_orders": synthetic, "imported_orders": imported,
        "last_import": None if last is None else {"id": last.id, "filename": last.filename, "status": last.status,
                                                  "source": last.source, "finished_at": last.finished_at},
        "database_backend": settings.database_backend, "read_only": settings.read_only_mode,
        "ai_configured": settings.gemini_configured, "ai_model": settings.gemini_model or None,
        "automation_configured": bool(settings.automation_api_key),
        "single_organization": True,
    }
