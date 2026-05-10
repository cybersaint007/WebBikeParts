"""seed engine cover terms in parts_glossary

Revision ID: 0008_glossary_engine_covers
Revises: 0007_parts_glossary
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_glossary_engine_covers"
down_revision = "0007_parts_glossary"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


_TERMS = [
    ("generator-cover",      "generator cover",      "發電機外蓋",   "ジェネレーターカバー"),
    ("crankshaft-end-cover", "crankshaft end cover", "曲軸端蓋",     "クランクシャフトエンドカバー"),
    ("clutch-cover",         "clutch cover",         "離合器外蓋",   "クラッチカバー"),
    ("valve-cover",          "valve cover",          "汽門蓋",       "バルブカバー"),
    ("timing-cover",         "timing cover",         "正時蓋",       "タイミングカバー"),
    ("stator-cover",         "stator cover",         "定子蓋",       "ステーターカバー"),
    ("ignition-cover",       "ignition cover",       "點火器蓋",     "イグニッションカバー"),
    ("rocker-cover",         "rocker cover",         "搖臂蓋",       "ロッカーカバー"),
    ("oil-filter-cover",     "oil filter cover",     "機油濾芯蓋",   "オイルフィルターカバー"),
    ("engine-side-covers",   "engine side covers",   "引擎側蓋",     "エンジンサイドカバー"),
    ("engine-side-cases",    "engine side cases",    "引擎側殼",     "エンジンサイドケース"),
]


def upgrade() -> None:
    rows = ", ".join(
        f"('{slug}', '{en}', '{zh}', '{ja}', 'engine', 'seed')"
        for slug, en, zh, ja in _TERMS
    )
    op.execute(sa.text(
        f"INSERT INTO {SCHEMA}.parts_glossary (slug, term_en, term_zh, term_ja, category, source) "
        f"VALUES {rows} ON CONFLICT (slug) DO NOTHING"
    ))


def downgrade() -> None:
    slugs = ", ".join(f"'{slug}'" for slug, *_ in _TERMS)
    op.execute(sa.text(
        f"DELETE FROM {SCHEMA}.parts_glossary WHERE slug IN ({slugs}) AND source = 'seed'"
    ))
