from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.adapters import EbayAdapter, ManualSearchAdapter, WebikeAdapter, YahooAuctionsAdapter
from motorcycle_parts_watcher.bikes import BikeRef, load_active_bikes, load_bike_by_key
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.models import Source
from motorcycle_parts_watcher.services.ingest import IngestService


logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    bike_key: str
    total_found: int = 0
    total_ingested: int = 0
    source_breakdown: dict[str, int] = field(default_factory=dict)
    query: str | None = None


@dataclass
class WatchSpec:
    bike_key: str
    query: str
    watch_ids: list[int] = field(default_factory=list)


class CrawlService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.ingest = IngestService(session)
        self.adapters = [
            EbayAdapter(settings),
            YahooAuctionsAdapter(settings),
            WebikeAdapter(settings),
            ManualSearchAdapter(settings),
        ]

    async def crawl_bike(self, catalog_key: str, query: str | None = None) -> CrawlResult:
        bike = load_bike_by_key(self.session, catalog_key)
        if bike is None:
            raise ValueError(f"Unknown catalog_key: {catalog_key}")
        return await self._crawl_one(bike, query)

    async def crawl_all(self, query: str | None = None, include_watches: bool = True) -> list[CrawlResult]:
        bikes = load_active_bikes(self.session)
        results: list[CrawlResult] = []
        for bike in bikes:
            try:
                results.append(await self._crawl_one(bike, query))
            except Exception:
                logger.exception("crawl failed for %s", bike.catalog_key)

        if include_watches and query is None:
            results.extend(await self.crawl_watches())
        return results

    async def crawl_watches(self) -> list[CrawlResult]:
        """Pass 2: re-crawl every active high-priority watch entry, deduped per (bike, query)."""
        watches = self._load_active_watches()
        results: list[CrawlResult] = []
        for spec in watches:
            bike = load_bike_by_key(self.session, spec.bike_key)
            if bike is None:
                logger.warning("watch references unknown bike %s; skipping", spec.bike_key)
                continue
            try:
                result = await self._crawl_one(bike, spec.query)
                result.query = spec.query
                results.append(result)
                self._update_watch_metrics(spec, result.total_ingested)
            except Exception:
                logger.exception("watch crawl failed for %s q=%r", spec.bike_key, spec.query)
        self.session.commit()
        return results

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
        return [WatchSpec(bike_key=r["catalog_key"], query=r["query"], watch_ids=list(r["watch_ids"])) for r in rows]

    def _update_watch_metrics(self, spec: WatchSpec, ingested: int) -> None:
        if not spec.watch_ids:
            return
        # last_crawled_at always advances; match_count uses the rough # of new/updated rows.
        self.session.execute(
            text("""
                UPDATE console.parts_watches
                   SET last_crawled_at = now(),
                       match_count = :count,
                       updated_at = now()
                 WHERE id = ANY(:ids)
            """),
            {"count": ingested, "ids": spec.watch_ids},
        )

    async def _crawl_one(self, bike: BikeRef, query: str | None) -> CrawlResult:
        enabled_sources = {
            src.name for src in self.session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        }
        active_adapters = [
            a for a in self.adapters if a.enabled and a.name in enabled_sources
        ]
        result = CrawlResult(bike_key=bike.catalog_key)

        tasks = [adapter.fetch(bike, query) for adapter in active_adapters]
        batches = await asyncio.gather(*tasks, return_exceptions=True)

        for adapter, batch in zip(active_adapters, batches, strict=True):
            if isinstance(batch, Exception):
                logger.warning("adapter %s failed for %s: %s", adapter.name, bike.catalog_key, batch)
                continue
            result.source_breakdown[adapter.name] = len(batch)
            result.total_found += len(batch)
            for listing in batch:
                self.ingest.ingest_listing(listing)
                result.total_ingested += 1

        self.session.commit()
        return result
