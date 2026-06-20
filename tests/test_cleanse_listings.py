"""DB-gated tests for the listings cleanse helper.

Skipped automatically when DATABASE_URL is unset or migrations are missing.
See tests/conftest.py for fixtures.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from motorcycle_parts_watcher.services import listings


@pytest.fixture
def listing_factory(db_session):
    """Insert listings with controllable source/age/status; clean up on teardown.

    Returns a callable (source, days_old, status='active', snapshot=False) -> id.
    `days_old` sets both last_seen_at and (so the row is self-consistent) is the
    knob the cleanse keys off. Sources are namespaced per-test to avoid colliding
    with real data or other tests' fresh/stale source partitioning.
    """
    suffix = uuid.uuid4().hex[:8]
    created: list[int] = []

    def make(source: str, days_old: float, *, status: str = "active", snapshot: bool = False) -> int:
        src = f"{source}-{suffix}"
        key = uuid.uuid4().hex
        row = db_session.execute(
            text("""
                INSERT INTO watcher.listings
                    (source_name, bike_key, title, url, category, listing_status,
                     first_seen_at, last_seen_at, raw_json, content_hash)
                VALUES
                    (:src, 'test-bike', 'Test part', :url, 'unknown', :status,
                     now() - (:d || ' days')::interval,
                     now() - (:d || ' days')::interval,
                     '{}'::json, :hash)
                RETURNING id
            """),
            {"src": src, "url": f"https://example.test/{key}", "status": status,
             "d": days_old, "hash": key},
        ).scalar_one()
        created.append(row)
        if snapshot:
            db_session.execute(
                text("""
                    INSERT INTO watcher.listing_snapshots
                        (listing_id, checked_at, raw_json)
                    VALUES (:lid, now() - (:d || ' days')::interval, '{}'::json)
                """),
                {"lid": row, "d": days_old},
            )
        db_session.commit()
        return row

    def src_name(source: str) -> str:
        return f"{source}-{suffix}"

    make.src_name = src_name  # type: ignore[attr-defined]
    yield make

    if created:
        db_session.execute(
            text("DELETE FROM watcher.listings WHERE id = ANY(:ids)"),
            {"ids": created},
        )
        db_session.commit()


def _exists(db_session, listing_id: int) -> bool:
    return db_session.execute(
        text("SELECT 1 FROM watcher.listings WHERE id = :i"), {"i": listing_id}
    ).first() is not None


def test_deletes_stale_rows_in_fresh_source(db_session, listing_factory):
    fresh = listing_factory("ebay", 0.1)      # keeps the source "fresh"
    stale = listing_factory("ebay", 30)       # past the threshold

    result = listings.cleanse_stale(db_session, older_than_days=14, freshness_window_days=2)
    db_session.commit()

    assert not _exists(db_session, stale)
    assert _exists(db_session, fresh)
    assert result.deleted >= 1
    assert result.per_source.get(listing_factory.src_name("ebay")) == 1


def test_skips_source_with_no_recent_activity(db_session, listing_factory):
    """A blocked adapter: every row is stale, newest still older than the window."""
    a = listing_factory("webike_search", 20)
    b = listing_factory("webike_search", 40)

    result = listings.cleanse_stale(db_session, older_than_days=14, freshness_window_days=2)
    db_session.commit()

    assert _exists(db_session, a)
    assert _exists(db_session, b)
    assert listing_factory.src_name("webike_search") in result.skipped_sources
    assert listing_factory.src_name("webike_search") not in result.per_source


def test_manual_seed_rows_are_exempt(db_session, listing_factory):
    listing_factory("manual_search", 0.1)                       # keeps source fresh
    seed = listing_factory("manual_search", 60, status="manual_seed")

    listings.cleanse_stale(db_session, older_than_days=14, freshness_window_days=2)
    db_session.commit()

    assert _exists(db_session, seed)


def test_dry_run_deletes_nothing_but_reports_counts(db_session, listing_factory):
    listing_factory("ebay", 0.1)
    stale = listing_factory("ebay", 30)

    result = listings.cleanse_stale(
        db_session, older_than_days=14, freshness_window_days=2, dry_run=True
    )
    db_session.commit()

    assert result.dry_run is True
    assert result.deleted >= 1
    assert result.per_source.get(listing_factory.src_name("ebay")) == 1
    assert _exists(db_session, stale)  # nothing actually deleted


def test_delete_cascades_to_snapshots(db_session, listing_factory):
    listing_factory("ebay", 0.1)
    stale = listing_factory("ebay", 30, snapshot=True)

    snap_before = db_session.execute(
        text("SELECT COUNT(*) FROM watcher.listing_snapshots WHERE listing_id = :i"),
        {"i": stale},
    ).scalar_one()
    assert snap_before == 1

    listings.cleanse_stale(db_session, older_than_days=14, freshness_window_days=2)
    db_session.commit()

    snap_after = db_session.execute(
        text("SELECT COUNT(*) FROM watcher.listing_snapshots WHERE listing_id = :i"),
        {"i": stale},
    ).scalar_one()
    assert snap_after == 0
