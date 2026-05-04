from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations_to_head() -> None:
    alembic_ini = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(alembic_ini))
    command.upgrade(cfg, "head")

