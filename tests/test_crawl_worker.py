"""DB-gated worker tests.

Uses a fake adapter injected into the worker's adapter map so we don't hit any
external services.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text

from motorcycle_parts_watcher.config import get_settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.services import job_queue
from motorcycle_parts_watcher.services.crawl import CrawlWorker


class _FakeAdapter:
    name = "test_fake"
    enabled = True
    preferred_query_lang = None

    def __init__(self, listings=None, exc=None):
        self._listings = listings or []
        self._exc = exc

    async def fetch(self, bike, query=None):
        if self._exc:
            raise self._exc
        return list(self._listings)


def _make_listing(bike_key: str, idx: int) -> NormalizedListing:
    suffix = uuid.uuid4().hex[:8]
    return NormalizedListing(
        source_name="test_fake",
        source_item_id=f"{suffix}-{idx}",
        bike_key=bike_key,
        title=f"Test listing {idx} {suffix}",
        url=f"https://example.test/listing/{suffix}-{idx}",
    )


def _build_worker(session_factory, *, adapter):
    w = CrawlWorker(
        session_factory=session_factory,
        settings=get_settings(),
        worker_id="test-worker",
        adapters=[adapter.name],
    )
    w._adapter_by_name = {adapter.name: adapter}  # bypass real adapter construction
    return w


def test_worker_processes_a_job_and_marks_completed(db_session_factory, test_bike, queue_tag):
    listings = [_make_listing(test_bike, 1), _make_listing(test_bike, 2)]
    adapter = _FakeAdapter(listings=listings)
    worker = _build_worker(db_session_factory, adapter=adapter)

    with db_session_factory() as s:
        job_id = job_queue.enqueue(s, adapter=adapter.name, bike_catalog_key=test_bike,
                                   query=None, enqueued_by=queue_tag)
        s.commit()

    had_work = asyncio.run(worker.run_once())
    assert had_work is True

    with db_session_factory() as s:
        row = s.execute(
            text("""SELECT status, result_found, result_ingested, last_error
                      FROM watcher.crawl_jobs WHERE id=:i"""),
            {"i": job_id},
        ).mappings().one()
    assert row["status"] == "completed"
    assert row["result_found"] == 2
    assert row["result_ingested"] == 2
    assert row["last_error"] is None


def test_worker_returns_false_when_queue_empty_for_adapter(db_session_factory, queue_tag):
    adapter = _FakeAdapter(listings=[])
    # Don't enqueue anything for this adapter; queue is empty for "test_fake".
    worker = _build_worker(db_session_factory, adapter=adapter)
    had_work = asyncio.run(worker.run_once())
    assert had_work is False


def test_worker_records_failure_on_adapter_exception(db_session_factory, test_bike, queue_tag):
    adapter = _FakeAdapter(exc=RuntimeError("simulated adapter failure"))
    worker = _build_worker(db_session_factory, adapter=adapter)

    with db_session_factory() as s:
        # max_attempts=1 so we get a terminal 'failed' on the first try.
        job_id = job_queue.enqueue(s, adapter=adapter.name, bike_catalog_key=test_bike,
                                   query=None, enqueued_by=queue_tag)
        s.execute(text("UPDATE watcher.crawl_jobs SET max_attempts=1 WHERE id=:i"),
                  {"i": job_id})
        s.commit()

    asyncio.run(worker.run_once())

    with db_session_factory() as s:
        row = s.execute(
            text("SELECT status, last_error FROM watcher.crawl_jobs WHERE id=:i"),
            {"i": job_id},
        ).mappings().one()
    assert row["status"] == "failed"
    assert "simulated adapter failure" in (row["last_error"] or "")


def test_worker_skips_jobs_outside_its_adapter_allowlist(db_session_factory, test_bike, queue_tag):
    adapter = _FakeAdapter(listings=[])
    worker = _build_worker(db_session_factory, adapter=adapter)

    # Job for some *other* adapter — worker should not pick it up.
    other_adapter_name = f"other_{uuid.uuid4().hex[:6]}"
    with db_session_factory() as s:
        other_id = job_queue.enqueue(s, adapter=other_adapter_name, bike_catalog_key=test_bike,
                                     query=None, enqueued_by=queue_tag)
        s.commit()

    had_work = asyncio.run(worker.run_once())
    assert had_work is False  # nothing claimable for our allowlist

    with db_session_factory() as s:
        status = s.execute(
            text("SELECT status FROM watcher.crawl_jobs WHERE id=:i"),
            {"i": other_id},
        ).scalar_one()
    assert status == "pending"
