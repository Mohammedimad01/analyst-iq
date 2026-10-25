from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import DbSession, OrgId
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.models import DataImport
from app.schemas import ImportList, ImportRead
from app.services.ingestion.importer import run_import
from app.services.ingestion.parsing import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/data/imports", tags=["data"])


@router.post("", response_model=ImportRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("upload", 10))])
def create_import(db: DbSession, org_id: OrgId, file: Annotated[UploadFile, File()],
                  replace: Annotated[bool, Form()] = False):
    settings = get_settings()
    if settings.read_only_mode:
        raise AppError(403, "Uploads are disabled in this deployment (read-only demo). Load data with the CLI.",
                       code="read_only")
    filename = PurePath(file.filename or "").name
    if PurePath(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise AppError(400, "Unsupported file type. Upload a .csv or .xlsx file.")
    limit = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise AppError(413, f"File is larger than {settings.max_upload_mb} MB.")
    if not content:
        raise AppError(400, "The uploaded file is empty.")
    return run_import(db, org_id, filename, content, settings.max_import_rows, source="upload", replace=replace)


@router.get("", response_model=ImportList)
def list_imports(db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0)] = 0):
    scope = DataImport.organization_id == org_id
    total = db.scalar(select(func.count()).select_from(DataImport).where(scope))
    items = db.scalars(select(DataImport).where(scope).order_by(DataImport.id.desc()).limit(limit).offset(offset))
    return {"total": total, "limit": limit, "offset": offset, "items": list(items)}


@router.get("/{import_id}", response_model=ImportRead)
def get_import(import_id: int, db: DbSession, org_id: OrgId):
    record = db.get(DataImport, import_id)
    if record is None or record.organization_id != org_id:
        raise AppError(404, "Import not found.")
    return record
