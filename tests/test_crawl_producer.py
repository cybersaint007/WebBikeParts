"""DB-gated producer tests.

Verifies that CrawlProducer translates the query per adapter and writes the
expected jobs to watcher.crawl_jobs.
"""
from __future__ import annotations

from sqlalchemy import text

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import get_settings
from motorcycle_parts_watcher.services import job_queue
from motorcycle_parts_watcher.services.crawl import CrawlProducer


def _settings():
    return get_settings()


class _FakeAdapter:
    def __init__(self, name, lang=None):
        self.name = name
        self.enabled = True
        self.preferred_query_lang = lang


def _patch_eligible(producer, fakes):
    producer._eligible_adapters = lambda: fakes  # type: ignore[method-assign]


def test_enqueue_for_bike_creates_one_job_per_eligible_adapter(db_session, test_bike, queue_tag):
    producer = CrawlProducer(db_session, settings=_settings())
    fakes = [_FakeAdapter("ebay", "en"), _FakeAdapter("webike_jp", "ja")]
    _patch_eligible(producer, fakes)

    summary = producer.enqueue_for_bike(test_bike, query="exhaust", enqueued_by=queue_tag)
    assert summary.total_enqueued == 2
    assert summary.by_adapter == {"ebay": 1, "webike_jp": 1}

    rows = db_session.execute(
        text("""SELECT adapter, query, original_query
                  FROM watcher.crawl_jobs WHERE enqueued_by=:t ORDER BY adapter"""),
        {"t": queue_tag},
    ).mappings().all()
    by_adapter = {r["adapter"]: dict(r) for r in rows}
    assert by_adapter["ebay"]["query"] == "exhaust"
    assert by_adapter["ebay"]["original_query"] == "exhaust"
    assert by_adapter["webike_jp"]["query"] == "マフラー"  # translated to JA
    assert by_adapter["webike_jp"]["original_query"] == "exhaust"  # preserved verbatim


def test_enqueue_for_bike_no_query_writes_null_query(db_session, test_bike, queue_tag):
    producer = CrawlProducer(db_session, settings=_settings())
    _patch_eligible(producer, [_FakeAdapter("ebay", "en"), _FakeAdapter("webike_jp", "ja")])

    summary = producer.enqueue_for_bike(test_bike, enqueued_by=queue_tag)
    assert summary.total_enqueued == 2

    rows = db_session.execute(
        text("SELECT query FROM watcher.crawl_jobs WHERE enqueued_by=:t"),
        {"t": queue_tag},
    ).mappings().all()
    assert all(r["query"] is None for r in rows)


def test_enqueue_for_bike_dedup_skips_inflight(db_session, test_bike, queue_tag):
    producer = CrawlProducer(db_session, settings=_settings())
    _patch_eligible(producer, [_FakeAdapter("ebay", "en")])

    s1 = producer.enqueue_for_bike(test_bike, query="exhaust", enqueued_by=queue_tag)
    assert s1.total_enqueued == 1
    s2 = producer.enqueue_for_bike(test_bike, query="exhaust", enqueued_by=queue_tag)
    assert s2.total_enqueued == 0
    assert s2.skipped.get("ebay") == 1


def test_enqueue_for_bike_zh_input_translates_for_each_adapter(db_session, test_bike, queue_tag):
    producer = CrawlProducer(db_session, settings=_settings())
    _patch_eligible(producer, [
        _FakeAdapter("ebay", "en"),
        _FakeAdapter("webike", "zh-TW"),
        _FakeAdapter("webike_jp", "ja"),
    ])
    summary = producer.enqueue_for_bike(test_bike, query="排氣管", enqueued_by=queue_tag)
    assert summary.total_enqueued == 3

    rows = db_session.execute(
        text("SELECT adapter, query FROM watcher.crawl_jobs WHERE enqueued_by=:t"),
        {"t": queue_tag},
    ).mappings().all()
    q_by = {r["adapter"]: r["query"] for r in rows}
    assert q_by["ebay"] == "exhaust"
    assert q_by["webike"] == "排氣管"   # source==target, no-op
    assert q_by["webike_jp"] == "マフラー"


def test_enqueue_unknown_bike_raises(db_session, queue_tag):
    producer = CrawlProducer(db_session, settings=_settings())
    _patch_eligible(producer, [_FakeAdapter("ebay", "en")])
    try:
        producer.enqueue_for_bike("does-not-exist", enqueued_by=queue_tag)
        assert False, "expected ValueError"
    except ValueError:
        pass
