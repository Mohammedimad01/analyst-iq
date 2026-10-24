from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Organization

DEMO_ORG_SLUG = "demo"


def get_demo_org_id(db: Session) -> int:
    """Milestone 1 runs a single demo organisation (no auth). Created on first use."""
    org_id = db.scalar(select(Organization.id).where(Organization.slug == DEMO_ORG_SLUG))
    if org_id is None:
        org = Organization(name=get_settings().organization_name, slug=DEMO_ORG_SLUG)
        db.add(org)
        db.commit()
        org_id = org.id
    return org_id


def data_mix(db: Session, org_id: int) -> tuple[str, int, int]:
    """("none" | "synthetic" | "imported" | "mixed", synthetic orders, imported orders)."""
    from sqlalchemy import func

    from app.models import DataImport, Order

    # Grouped on the raw column: PostgreSQL rejects GROUP BY coalesce(col, $1) when SELECT binds its own $2.
    by_source = dict(db.execute(
        select(DataImport.source, func.count(Order.id))
        .select_from(Order).outerjoin(DataImport, DataImport.id == Order.import_id)
        .where(Order.organization_id == org_id).group_by(DataImport.source)).all())
    synthetic = by_source.get("synthetic_demo", 0)
    imported = by_source.get("upload", 0) + by_source.get(None, 0)  # orders without an import record: treat as real
    kind = ("none" if not synthetic and not imported else "mixed" if synthetic and imported
            else "synthetic" if synthetic else "imported")
    return kind, synthetic, imported
