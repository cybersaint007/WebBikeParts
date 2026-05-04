"""Test fixtures for DB-gated tests.

Tests using these fixtures skip cleanly when DATABASE_URL is unset or the
crawl_jobs table is missing (e.g. `alembic upgrade head` hasn't been run).
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def _engine_or_skip():
    url = os.environ.get("DATABASE_URL") or ""
    if not url.startswith("postgresql+psycopg://"):
        pytest.skip("DATABASE_URL not set or not a postgresql+psycopg URL")
    try:
        engine = create_engine(url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM watcher.crawl_jobs LIMIT 1"))
        return engine
    except Exception as exc:
        pytest.skip(f"DB not reachable or migrations not applied: {exc}")


@pytest.fixture(scope="session")
def db_engine():
    return _engine_or_skip()


@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, class_=Session)


@pytest.fixture
def db_session(db_session_factory) -> Session:
    s = db_session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def queue_tag(db_engine):
    """Unique enqueued_by tag scoped to the test; cleans up its rows on teardown."""
    tag = f"test:{uuid.uuid4().hex[:12]}"
    yield tag
    with db_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM watcher.crawl_jobs WHERE enqueued_by = :t"),
            {"t": tag},
        )


@pytest.fixture
def test_bike(db_engine):
    """Insert a throwaway bike_catalog row; delete after the test."""
    key = f"test-bike-{uuid.uuid4().hex[:8]}"
    with db_engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO watcher.bike_catalog
                    (make, model, model_slug, year_start, year_end, catalog_key)
                VALUES ('TEST', 'Bike', 'bike', 2000, 2000, :k)
            """),
            {"k": key},
        )
    yield key
    with db_engine.begin() as conn:
        # Listings tied to this bike get cleared too, in case a worker test wrote any.
        conn.execute(text("DELETE FROM watcher.listings WHERE bike_key = :k"), {"k": key})
        conn.execute(text("DELETE FROM watcher.bike_catalog WHERE catalog_key = :k"), {"k": key})
