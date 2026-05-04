from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from motorcycle_parts_watcher.config import get_settings


settings = get_settings()
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args={"options": f"-csearch_path={settings.db_schema},public"},
)
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
