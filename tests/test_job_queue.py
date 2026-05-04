"""DB-gated tests for the crawl_jobs queue.

Skipped automatically when DATABASE_URL is unset or migrations are missing.
See tests/conftest.py for fixtures.
"""
from __future__ import annotations

from sqlalchemy import text

from motorcycle_parts_watcher.services import job_queue


def test_enqueue_returns_id_and_inserts_row(db_session, queue_tag):
    job_id = job_queue.enqueue(
        db_session, adapter="ebay", bike_catalog_key="bike-x",
        query="exhaust", priority=42, enqueued_by=queue_tag,
    )
    db_session.commit()
    assert job_id is not None

    row = db_session.execute(
        text("SELECT adapter, query, priority, status FROM watcher.crawl_jobs WHERE id=:i"),
        {"i": job_id},
    ).mappings().one()
    assert row["adapter"] == "ebay"
    assert row["query"] == "exhaust"
    assert row["priority"] == 42
    assert row["status"] == "pending"


def test_enqueue_dedup_blocks_inflight_duplicate(db_session, queue_tag):
    a = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    db_session.commit()
    # Same (adapter, bike, query) while still pending → blocked by partial UNIQUE.
    b = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    db_session.commit()
    assert a is not None
    assert b is None


def test_enqueue_dedup_treats_null_query_same_as_other_null_query(db_session, queue_tag):
    a = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query=None, enqueued_by=queue_tag)
    db_session.commit()
    b = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query=None, enqueued_by=queue_tag)
    db_session.commit()
    assert a is not None and b is None


def test_enqueue_different_adapter_or_bike_or_query_not_blocked(db_session, queue_tag):
    a = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    b = job_queue.enqueue(db_session, adapter="webike", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    c = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b2",
                          query="q", enqueued_by=queue_tag)
    d = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query="other", enqueued_by=queue_tag)
    db_session.commit()
    assert all(x is not None for x in (a, b, c, d))
    assert len({a, b, c, d}) == 4


def test_claim_next_filters_by_adapter(db_session, queue_tag):
    job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                      query="q1", enqueued_by=queue_tag)
    job_queue.enqueue(db_session, adapter="webike_jp", bike_catalog_key="b1",
                      query="q2", enqueued_by=queue_tag)
    db_session.commit()

    job = job_queue.claim_next(db_session, worker_id="w-jp", adapters=["webike_jp"])
    db_session.commit()
    assert job is not None
    assert job.adapter == "webike_jp"

    # Worker that doesn't handle webike_jp shouldn't see anything once we claim_next again
    # for ebay only — but should see the pending ebay job.
    job2 = job_queue.claim_next(db_session, worker_id="w-us", adapters=["ebay"])
    db_session.commit()
    assert job2 is not None
    assert job2.adapter == "ebay"


def test_claim_next_orders_by_priority_then_id(db_session, queue_tag):
    a = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b-a",
                          query="q", priority=100, enqueued_by=queue_tag)
    b = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b-b",
                          query="q", priority=50, enqueued_by=queue_tag)
    c = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b-c",
                          query="q", priority=50, enqueued_by=queue_tag)
    db_session.commit()
    j1 = job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"]); db_session.commit()
    j2 = job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"]); db_session.commit()
    j3 = job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"]); db_session.commit()
    assert [j.id for j in (j1, j2, j3)] == [b, c, a]


def test_claim_next_returns_none_when_empty(db_session, queue_tag):
    job = job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"])
    # The fixture-tagged rows are empty for our tag, but other tests may have left
    # ebay rows. Safest assertion: if a job was returned, it's *not* one of ours.
    if job is not None:
        assert job.enqueued_by != queue_tag
    # And: empty allowlist always yields None.
    assert job_queue.claim_next(db_session, worker_id="w", adapters=[]) is None


def test_claim_skip_locked_under_contention(db_session_factory, queue_tag):
    """Two sessions racing to claim should each get a different row."""
    s1 = db_session_factory()
    s2 = db_session_factory()
    try:
        job_queue.enqueue(s1, adapter="ebay", bike_catalog_key="ba",
                          query="q", enqueued_by=queue_tag)
        job_queue.enqueue(s1, adapter="ebay", bike_catalog_key="bb",
                          query="q", enqueued_by=queue_tag)
        s1.commit()

        # Begin both transactions, then claim in parallel.
        j1 = job_queue.claim_next(s1, worker_id="w1", adapters=["ebay"])
        j2 = job_queue.claim_next(s2, worker_id="w2", adapters=["ebay"])
        s1.commit(); s2.commit()
        assert j1 is not None and j2 is not None
        assert j1.id != j2.id
    finally:
        s1.close(); s2.close()


def test_complete_marks_terminal_and_records_counts(db_session, queue_tag):
    job_id = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                               query="q", enqueued_by=queue_tag)
    db_session.commit()
    job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"])
    db_session.commit()
    job_queue.complete(db_session, job_id, found=10, ingested=7)
    db_session.commit()

    row = db_session.execute(
        text("""SELECT status, result_found, result_ingested, completed_at
                  FROM watcher.crawl_jobs WHERE id=:i"""),
        {"i": job_id},
    ).mappings().one()
    assert row["status"] == "completed"
    assert row["result_found"] == 10
    assert row["result_ingested"] == 7
    assert row["completed_at"] is not None


def test_fail_retries_under_max_then_terminal(db_session, queue_tag):
    job_id = job_queue.enqueue(
        db_session, adapter="ebay", bike_catalog_key="b1",
        query="q", enqueued_by=queue_tag,
    )
    # Lower max_attempts to exercise the boundary cheaply.
    db_session.execute(
        text("UPDATE watcher.crawl_jobs SET max_attempts=2 WHERE id=:i"),
        {"i": job_id},
    )
    db_session.commit()

    # Attempt 1: claim → fail → should re-queue (status='pending').
    job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"])
    db_session.commit()
    status1 = job_queue.fail(db_session, job_id, error="boom")
    db_session.commit()
    assert status1 == "pending"

    # Attempt 2: claim → fail → terminal.
    job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"])
    db_session.commit()
    status2 = job_queue.fail(db_session, job_id, error="boom2")
    db_session.commit()
    assert status2 == "failed"

    row = db_session.execute(
        text("SELECT status, attempts, last_error FROM watcher.crawl_jobs WHERE id=:i"),
        {"i": job_id},
    ).mappings().one()
    assert row["status"] == "failed"
    assert row["attempts"] == 2
    assert "boom2" in row["last_error"]


def test_dedup_releases_after_terminal_state(db_session, queue_tag):
    """Once a job is completed/failed, an identical (adapter, bike, query) can be enqueued again."""
    j1 = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                           query="q", enqueued_by=queue_tag)
    db_session.commit()
    job_queue.claim_next(db_session, worker_id="w", adapters=["ebay"])
    db_session.commit()
    job_queue.complete(db_session, j1, found=0, ingested=0)
    db_session.commit()

    j2 = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                           query="q", enqueued_by=queue_tag)
    db_session.commit()
    assert j2 is not None and j2 != j1


def test_release_stale_returns_running_to_pending(db_session, queue_tag):
    job_id = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                               query="q", enqueued_by=queue_tag)
    db_session.commit()
    job_queue.claim_next(db_session, worker_id="w-dead", adapters=["ebay"])
    # Force locked_at into the past so release_stale picks it up.
    db_session.execute(
        text("UPDATE watcher.crawl_jobs SET locked_at = now() - interval '2 hours' WHERE id=:i"),
        {"i": job_id},
    )
    db_session.commit()

    n = job_queue.release_stale(db_session, stale_after_minutes=30)
    db_session.commit()
    assert n >= 1

    row = db_session.execute(
        text("SELECT status, locked_by FROM watcher.crawl_jobs WHERE id=:i"),
        {"i": job_id},
    ).mappings().one()
    assert row["status"] == "pending"
    assert row["locked_by"] is None


def test_jobs_for_enqueued_by_lists_all(db_session, queue_tag):
    a = job_queue.enqueue(db_session, adapter="ebay", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    b = job_queue.enqueue(db_session, adapter="webike", bike_catalog_key="b1",
                          query="q", enqueued_by=queue_tag)
    db_session.commit()
    rows = job_queue.jobs_for_enqueued_by(db_session, queue_tag)
    ids = {r["id"] for r in rows}
    assert {a, b} <= ids
