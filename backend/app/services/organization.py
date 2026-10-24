from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization

DEMO_ORG_SLUG = "demo"


def get_demo_org_id(db: Session) -> int:
    """Milestone 1 runs a single demo organisation (no auth). Created on first use."""
    org_id = db.scalar(select(Organization.id).where(Organization.slug == DEMO_ORG_SLUG))
    if org_id is None:
        org = Organization(name="Demo Retail Co (synthetic data)", slug=DEMO_ORG_SLUG)
        db.add(org)
        db.commit()
        org_id = org.id
    return org_id
