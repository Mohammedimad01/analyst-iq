"""reports and automation events

Revision ID: 0004_reports_automation
Revises: 0003_import_source
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_reports_automation"
down_revision: Union[str, Sequence[str], None] = "0003_import_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("report_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("contains_synthetic", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("report_type IN ('executive', 'sales', 'product', 'store', 'customer', 'profitability')",
                           name="ck_reports_type"),
        sa.CheckConstraint("file_format IN ('pdf', 'csv')", name="ck_reports_format"),
    )
    op.create_index("ix_reports_org_created", "reports", ["organization_id", "created_at"])
    op.create_table(
        "automation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workflow", sa.String(length=50), nullable=False),
        sa.Column("item_key", sa.String(length=250), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "workflow", "item_key"),
    )


def downgrade() -> None:
    op.drop_table("automation_events")
    op.drop_index("ix_reports_org_created", table_name="reports")
    op.drop_table("reports")
