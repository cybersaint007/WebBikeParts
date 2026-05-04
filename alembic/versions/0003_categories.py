"""categories taxonomy table

Revision ID: 0003_categories
Revises: 0002_bike_catalog
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_categories"
down_revision = "0002_bike_catalog"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("label_en", sa.String(length=150), nullable=False),
        sa.Column("label_zh", sa.String(length=150), nullable=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey(f"{SCHEMA}.categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("webike_url", sa.String(length=500), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
        schema=SCHEMA,
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"], schema=SCHEMA)
    op.create_index("ix_categories_slug", "categories", ["slug"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_categories_slug", table_name="categories", schema=SCHEMA)
    op.drop_index("ix_categories_parent_id", table_name="categories", schema=SCHEMA)
    op.drop_table("categories", schema=SCHEMA)
