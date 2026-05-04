from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.adapters import (
    CroooberAdapter,
    EbayAdapter,
    GoobikeAdapter,
    ManualSearchAdapter,
    MercariAdapter,
    MonotaroAdapter,
    RakutenAdapter,
    WebikeAdapter,
    WebikeJpAdapter,
    YahooAuctionsAdapter,
)
from motorcycle_parts_watcher.bikes import BikeRef, load_active_bikes, load_bike_by_key
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.models import Source
from motorcycle_parts_watcher.services import job_queue
from motorcycle_parts_watcher.services.ingest import IngestService
from motorcycle_parts_watcher.utils.i18n import translate_for_adapter


logger = logging.getLogger(__name__)


# Lower number = sooner (matches ORDER BY priority, id in claim_next).
PRIORITY_LIVE_SEARCH = 25   # user is staring at the UI
PRIORITY_WATCH_SWEEP = 50
PRIORITY_BIKE_SWEEP = 100


def _build_adapters(settings: Settings) -> list:
    return [
        EbayAdapter(settings),
        YahooAuctionsAdapter(settings),
        WebikeAdapter(settings),
        WebikeJpAdapter(settings),
        CroooberAdapter(settings),
        MercariAdapter(settings),
        RakutenAdapter(settings),
        MonotaroAdapter(settings),
        GoobikeAdapter(settings),
        ManualSearchAdapter(settings),
    ]


@dataclass
class EnqueueSummary:
    by_adapter: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    @property
    def total_enqueued(self) -> int:
        return sum(self.by_adapter.values())

    def merge(self, other: "EnqueueSummary") -> None:
        for k, v in other.by_adapter.items():
            self.by_adapter[k] = self.by_adapter.get(k, 0) + v
        for k, v in other.skipped.items():
            self.skipped[k] = self.skipped.get(k, 0) + v


@dataclass
class WatchSpec:
    bike_key: str
    query: str
    watch_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Producer: enqueues jobs only. Runs on the central host (or wherever the CLI /
# Laravel jobs run). Translates the query per adapter at enqueue time so the
# worker is dumb and stateless w.r.t. translation.
# ---------------------------------------------------------------------------


class CrawlProducer:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.adapters = _build_adapters(settings)

    def _eligible_adapters(self) -> list:
        enabled_sources = {
            src.name
            for src in self.session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        }
        return [a for a in self.adapters if a.enabled and a.name in enabled_sources]

    def enqueue_for_bike(
        self,
        catalog_key: str,
        *,
        query: str | None = None,
        priority: int | None = None,
        enqueued_by: str | None = None,
        watch_ids: list[int] | None = None,
    ) -> EnqueueSummary:
        bike = load_bike_by_key(self.session, catalog_key)
        if bike is None:
            raise ValueError(f"Unknown catalog_key: {catalog_key}")
        prio = priority if priority is not None else (
            PRIORITY_LIVE_SEARCH if query else PRIORITY_BIKE_SWEEP
        )
        summary = self._enqueue_one_bike(
            bike, query=query, priority=prio,
            enqueued_by=enqueued_by, watch_ids=watch_ids,
        )
        self.session.commit()
        return summary

    def enqueue_all(
        self,
        *,
        query: str | None = None,
        include_watches: bool = True,
        enqueued_by: str | None = None,
    ) -> EnqueueSummary:
        bikes = load_active_bikes(self.session)
        summary = EnqueueSummary()
        prio = PRIORITY_LIVE_SEARCH if query else PRIORITY_BIKE_SWEEP
        for bike in bikes:
            summary.merge(self._enqueue_one_bike(
                bike, query=query, priority=prio, enqueued_by=enqueued_by,
            ))
        if include_watches and query is None:
            summary.merge(self._enqueue_watches(enqueued_by=enqueued_by))
        self.session.commit()
        return summary

    def enqueue_watches(self, *, enqueued_by: str | None = None) -> EnqueueSummary:
        summary = self._enqueue_watches(enqueued_by=enqueued_by)
        self.session.commit()
        return summary

    def _enqueue_watches(self, *, enqueued_by: str | None) -> EnqueueSummary:
        watches = self._load_active_watches()
        summary = EnqueueSummary()
        for spec in watches:
            bike = load_bike_by_key(self.session, spec.bike_key)
            if bike is None:
                logger.warning("watch references unknown bike %s; skipping", spec.bike_key)
                continue
            summary.merge(self._enqueue_one_bike(
                bike,
                query=spec.query,
                priority=PRIORITY_WATCH_SWEEP,
                watch_ids=spec.watch_ids,
                enqueued_by=enqueued_by or "crawl-watches",
            ))
        return summary

    def _enqueue_one_bike(
        self,
        bike: BikeRef,
        *,
        query: str | None,
        priority: int,
        watch_ids: list[int] | None = None,
        enqueued_by: str | None = None,
    ) -> EnqueueSummary:
        summary = EnqueueSummary()
        for adapter in self._eligible_adapters():
            translated = translate_for_adapter(query, adapter) if query else None
            job_id = job_queue.enqueue(
                self.session,
                adapter=adapter.name,
                bike_catalog_key=bike.catalog_key,
                query=translated,
                original_query=query,
                priority=priority,
                watch_ids=watch_ids,
                enqueued_by=enqueued_by,
            )
            if job_id is not None:
                summary.by_adapter[adapter.name] = summary.by_adapter.get(adapter.name, 0) + 1
            else:
                summary.skipped[adapter.name] = summary.skipped.get(adapter.name, 0) + 1
        return summary

    def _load_active_watches(self) -> list[WatchSpec]:
        rows = self.session.execute(text("""
            SELECT bc.catalog_key,
                   pw.query,
                   array_agg(pw.id) AS watch_ids
              FROM console.parts_watches pw
              JOIN watcher.bike_catalog bc ON bc.id = pw.bike_catalog_id
             WHERE pw.is_high_priority = true
          GROUP BY bc.catalog_key, pw.query
        """)).mappings().all()
        return [
            WatchSpec(bike_key=r["catalog_key"], query=r["query"], watch_ids=list(r["watch_ids"]))
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Worker: claims jobs filtered by adapter allowlist, runs the adapter, ingests.
# Each job gets its own DB session so a long fetch doesn't hold a row lock,
# and a crash in one job doesn't poison subsequent ones.
# ---------------------------------------------------------------------------


SessionFactory = Callable[[], Session]


class CrawlWorker:
    DEFAULT_POLL_SECONDS = 5
    STALE_RELEASE_EVERY = 60  # iterations between stale-lock sweeps

    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        worker_id: str,
        adapters: list[str],
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.worker_id = worker_id
        self.adapters_allow = list(adapters)
        # Build only the adapters this worker handles.
        self._adapter_by_name = {
            a.name: a for a in _build_adapters(settings) if a.name in self.adapters_allow
        }

    @contextmanager
    def _session(self):
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    async def run_once(self) -> bool:
        """Claim and run a single job. Returns True if a job was processed (or attempted)."""
        with self._session() as session:
            job = job_queue.claim_next(
                session, worker_id=self.worker_id, adapters=self.adapters_allow,
            )
            session.commit()  # release row locks held by the UPDATE
            if job is None:
                return False

        try:
            await self._run_job(job)
        except Exception as exc:
            logger.exception("worker %s: job %s crashed", self.worker_id, job.id)
            with self._session() as session:
                job_queue.fail(session, job.id, error=f"{type(exc).__name__}: {exc}")
                session.commit()
        return True

    async def _run_job(self, job) -> None:
        adapter = self._adapter_by_name.get(job.adapter)
        if adapter is None:
            with self._session() as session:
                job_queue.fail(
                    session, job.id,
                    error=f"adapter {job.adapter!r} not configured on worker {self.worker_id!r}",
                )
                session.commit()
            return

        with self._session() as session:
            bike = load_bike_by_key(session, job.bike_catalog_key)
            if bike is None:
                job_queue.fail(session, job.id, error=f"unknown bike {job.bike_catalog_key}")
                session.commit()
                return

            try:
                listings = await adapter.fetch(bike, job.query)
            except Exception as exc:
                logger.warning(
                    "adapter %s failed for %s: %s", adapter.name, bike.catalog_key, exc,
                )
                job_queue.fail(session, job.id, error=f"adapter error: {exc}")
                session.commit()
                return

            ingest = IngestService(session)
            ingested = 0
            for listing in listings:
                ingest.ingest_listing(listing)
                ingested += 1

            if job.watch_ids:
                # match_count is additive across per-adapter completions (semantic A=i):
                # every completing watch-job adds its ingest count, last_crawled_at advances.
                session.execute(
                    text("""
                        UPDATE console.parts_watches
                           SET last_crawled_at = now(),
                               match_count = COALESCE(match_count, 0) + :delta,
                               updated_at = now()
                         WHERE id = ANY(:ids)
                    """),
                    {"delta": ingested, "ids": list(job.watch_ids)},
                )

            job_queue.complete(session, job.id, found=len(listings), ingested=ingested)
            session.commit()

    async def run_forever(self, *, poll_seconds: int | None = None) -> None:
        wait = poll_seconds or self.DEFAULT_POLL_SECONDS
        i = 0
        while True:
            had_work = await self.run_once()
            i += 1
            if i % self.STALE_RELEASE_EVERY == 0:
                with self._session() as session:
                    n = job_queue.release_stale(session)
                    session.commit()
                    if n:
                        logger.info(
                            "worker %s: released %d stale jobs", self.worker_id, n,
                        )
            if not had_work:
                await asyncio.sleep(wait)
