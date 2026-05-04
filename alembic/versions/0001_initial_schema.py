"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    op.create_table(
        "bikes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("make", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("variant", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("name", name="uq_sources_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_item_id", sa.String(length=255), nullable=True),
        sa.Column("bike_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_currency", sa.String(length=10), nullable=True),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("seller_name", sa.String(length=255), nullable=True),
        sa.Column("seller_country", sa.String(length=100), nullable=True),
        sa.Column("condition", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        sa.Column("part_number", sa.String(length=100), nullable=True),
        sa.Column("fitment_text", sa.Text(), nullable=True),
        sa.Column("listing_status", sa.String(length=100), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("url", name="uq_listings_url"),
        sa.UniqueConstraint("source_name", "source_item_id", name="uq_listings_source_item"),
        schema=SCHEMA,
    )
    op.create_index("ix_listings_source_name", "listings", ["source_name"], schema=SCHEMA)
    op.create_index("ix_listings_source_item_id", "listings", ["source_item_id"], schema=SCHEMA)
    op.create_index("ix_listings_bike_key", "listings", ["bike_key"], schema=SCHEMA)
    op.create_index("ix_listings_category", "listings", ["category"], schema=SCHEMA)
    op.create_index("ix_listings_part_number", "listings", ["part_number"], schema=SCHEMA)
    op.create_index("ix_listings_content_hash", "listings", ["content_hash"], schema=SCHEMA)

    op.create_table(
        "listing_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "listing_id",
            sa.Integer(),
            sa.ForeignKey(f"{SCHEMA}.listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("availability_status", sa.String(length=100), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_listing_snapshots_listing_id", "listing_snapshots", ["listing_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_listing_snapshots_listing_id", table_name="listing_snapshots", schema=SCHEMA)
    op.drop_table("listing_snapshots", schema=SCHEMA)
    op.drop_index("ix_listings_content_hash", table_name="listings", schema=SCHEMA)
    op.drop_index("ix_listings_part_number", table_name="listings", schema=SCHEMA)
    op.drop_index("ix_listings_category", table_name="listings", schema=SCHEMA)
    op.drop_index("ix_listings_bike_key", table_name="listings", schema=SCHEMA)
    op.drop_index("ix_listings_source_item_id", table_name="listings", schema=SCHEMA)
    op.drop_index("ix_listings_source_name", table_name="listings", schema=SCHEMA)
    op.drop_table("listings", schema=SCHEMA)
    op.drop_table("sources", schema=SCHEMA)
    op.drop_table("bikes", schema=SCHEMA)
