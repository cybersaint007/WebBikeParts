"""Add image_url to bike_catalog

Revision ID: 0006_bike_catalog_image
Revises: 0005_crawl_jobs
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_bike_catalog_image"
down_revision = "0005_crawl_jobs"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.add_column(
        "bike_catalog",
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("bike_catalog", "image_url", schema=SCHEMA)
