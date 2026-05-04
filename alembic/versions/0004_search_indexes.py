"""pg_trgm extension + GIN indexes for fast ILIKE search

Revision ID: 0004_search_indexes
Revises: 0003_categories
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_search_indexes"
down_revision = "0003_categories"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    op.execute(sa.text(
        f"CREATE INDEX IF NOT EXISTS listings_title_trgm_idx "
        f"ON {SCHEMA}.listings USING gin (title gin_trgm_ops)"
    ))
    op.execute(sa.text(
        f"CREATE INDEX IF NOT EXISTS listings_description_trgm_idx "
        f"ON {SCHEMA}.listings USING gin (description gin_trgm_ops)"
    ))
    op.execute(sa.text(
        f"CREATE INDEX IF NOT EXISTS listings_part_number_trgm_idx "
        f"ON {SCHEMA}.listings USING gin (part_number gin_trgm_ops)"
    ))


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.listings_part_number_trgm_idx"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.listings_description_trgm_idx"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.listings_title_trgm_idx"))
