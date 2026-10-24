"""import source (upload vs synthetic demo)

Revision ID: 0003_import_source
Revises: 8793018011f3
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_import_source"
down_revision: Union[str, Sequence[str], None] = "8793018011f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("data_imports") as batch:
        batch.add_column(sa.Column("source", sa.String(length=30), nullable=False, server_default="upload"))
        batch.create_check_constraint("ck_data_imports_source", "source IN ('upload', 'synthetic_demo')")
    # Backfill: before this column existed, the demo dataset was only ever loaded by `app.cli seed` from this file.
    op.execute("UPDATE data_imports SET source = 'synthetic_demo' WHERE filename = 'retail_sample.csv'")
    # "Synthetic" now describes the data (above), not the organisation name.
    op.execute("UPDATE organizations SET name = 'Demo Retail Co' WHERE name = 'Demo Retail Co (synthetic data)'")


def downgrade() -> None:
    with op.batch_alter_table("data_imports") as batch:
        batch.drop_constraint("ck_data_imports_source", type_="check")
        batch.drop_column("source")
