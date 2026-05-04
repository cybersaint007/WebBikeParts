"""bike_catalog table + bike_catalog_id on bikes + legacy backfill

Revision ID: 0002_bike_catalog
Revises: 0001_initial_schema
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_bike_catalog"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.create_table(
        "bike_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("make", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("model_slug", sa.String(length=150), nullable=False),
        sa.Column("year_start", sa.Integer(), nullable=False),
        sa.Column("year_end", sa.Integer(), nullable=False),
        sa.Column("displacement_cc", sa.Integer(), nullable=True),
        sa.Column("webike_url", sa.String(length=500), nullable=True),
        sa.Column("catalog_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("catalog_key", name="uq_bike_catalog_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bike_catalog_make", "bike_catalog", ["make"], schema=SCHEMA)
    op.create_index("ix_bike_catalog_model_slug", "bike_catalog", ["model_slug"], schema=SCHEMA)
    op.create_index("ix_bike_catalog_years", "bike_catalog", ["year_start", "year_end"], schema=SCHEMA)

    op.add_column(
        "bikes",
        sa.Column("bike_catalog_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_bikes_bike_catalog",
        "bikes",
        "bike_catalog",
        ["bike_catalog_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )

    # Backfill: seed legacy katana / hayabusa as catalog rows, link bikes, update listings.bike_key
    op.execute(sa.text(f"""
        INSERT INTO {SCHEMA}.bike_catalog (make, model, model_slug, year_start, year_end, displacement_cc, catalog_key)
        VALUES
            ('SUZUKI', 'Katana 1100', 'katana-1100', 1990, 1990, 1100, 'suzuki-katana-1100-1990'),
            ('SUZUKI', 'GSX1300R',    'gsx1300r',    2003, 2003, 1300, 'suzuki-gsx1300r-2003')
        ON CONFLICT (catalog_key) DO NOTHING
    """))

    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.bikes b
           SET bike_catalog_id = bc.id
          FROM {SCHEMA}.bike_catalog bc
         WHERE bc.catalog_key = 'suzuki-katana-1100-1990'
           AND lower(b.model) LIKE '%katana%'
           AND b.year = 1990
    """))

    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.bikes b
           SET bike_catalog_id = bc.id
          FROM {SCHEMA}.bike_catalog bc
         WHERE bc.catalog_key = 'suzuki-gsx1300r-2003'
           AND b.model = 'GSX1300R'
           AND b.year = 2003
    """))

    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.listings
           SET bike_key = 'suzuki-katana-1100-1990'
         WHERE bike_key = 'katana1100'
    """))
    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.listings
           SET bike_key = 'suzuki-gsx1300r-2003'
         WHERE bike_key = 'hayabusa2003'
    """))


def downgrade() -> None:
    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.listings
           SET bike_key = 'katana1100'
         WHERE bike_key = 'suzuki-katana-1100-1990'
    """))
    op.execute(sa.text(f"""
        UPDATE {SCHEMA}.listings
           SET bike_key = 'hayabusa2003'
         WHERE bike_key = 'suzuki-gsx1300r-2003'
    """))
    op.drop_constraint("fk_bikes_bike_catalog", "bikes", schema=SCHEMA, type_="foreignkey")
    op.drop_column("bikes", "bike_catalog_id", schema=SCHEMA)
    op.drop_index("ix_bike_catalog_years", table_name="bike_catalog", schema=SCHEMA)
    op.drop_index("ix_bike_catalog_model_slug", table_name="bike_catalog", schema=SCHEMA)
    op.drop_index("ix_bike_catalog_make", table_name="bike_catalog", schema=SCHEMA)
    op.drop_table("bike_catalog", schema=SCHEMA)
