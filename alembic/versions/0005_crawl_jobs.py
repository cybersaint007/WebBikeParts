"""crawl_jobs queue table for distributed workers

Revision ID: 0005_crawl_jobs
Revises: 0004_search_indexes
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_crawl_jobs"
down_revision = "0004_search_indexes"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bike_catalog_key", sa.String(length=200), nullable=False),
        sa.Column("adapter", sa.String(length=50), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("original_query", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result_found", sa.Integer(), nullable=True),
        sa.Column("result_ingested", sa.Integer(), nullable=True),
        sa.Column("watch_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("enqueued_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    # Worker claim path: WHERE status='pending' AND adapter = ANY(...) ORDER BY priority, id
    op.create_index(
        "ix_crawl_jobs_claim",
        "crawl_jobs",
        ["status", "adapter", "priority", "id"],
        schema=SCHEMA,
    )

    # Health/visibility queries (counts of in-flight rows by status).
    op.execute(sa.text(f"""
        CREATE INDEX ix_crawl_jobs_active_status
            ON {SCHEMA}.crawl_jobs (status)
         WHERE status IN ('pending', 'running')
    """))

    op.create_index(
        "ix_crawl_jobs_enqueued_by",
        "crawl_jobs",
        ["enqueued_by"],
        schema=SCHEMA,
    )

    # Dedup: don't enqueue the same (adapter, bike, query) twice while it's still in
    # flight. COALESCE(query,'') so the partial unique covers bike-sweep jobs (query IS NULL).
    op.execute(sa.text(f"""
        CREATE UNIQUE INDEX uq_crawl_jobs_inflight
            ON {SCHEMA}.crawl_jobs (adapter, bike_catalog_key, COALESCE(query, ''))
         WHERE status IN ('pending', 'running')
    """))


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.uq_crawl_jobs_inflight"))
    op.drop_index("ix_crawl_jobs_enqueued_by", table_name="crawl_jobs", schema=SCHEMA)
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.ix_crawl_jobs_active_status"))
    op.drop_index("ix_crawl_jobs_claim", table_name="crawl_jobs", schema=SCHEMA)
    op.drop_table("crawl_jobs", schema=SCHEMA)
