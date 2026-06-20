"""Maintenance helpers for the watcher.listings table.

The crawler keeps `listings.last_seen_at` current: IngestService stamps it on
every re-discovery (services/ingest.py). When a source listing disappears — an
eBay/Yahoo auction expires, a part sells out — the next crawl no longer returns
it, so its `last_seen_at` stops advancing. That makes "unseen for N days" a
reliable staleness signal with no schema change.

`cleanse_stale` hard-deletes those rows (snapshots cascade via the
listing_snapshots FK ondelete=CASCADE), but only from sources that show recent
crawl activity. If a worker dies or an adapter is blocked, *every* row for that
source goes stale at once; deleting them would wipe still-live listings. The
per-source freshness guard skips any source whose newest listing is itself older
than the freshness window — the crawler, not the listings, is the problem there.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

DEFAULT_OLDER_THAN_DAYS = 14
DEFAULT_FRESHNESS_WINDOW_DAYS = 2
DEFAULT_EXEMPT_STATUSES: tuple[str, ...] = ("manual_seed",)


@dataclass
class CleanseResult:
    """Outcome of a cleanse pass.

    deleted: total rows deleted (or that would be, when dry_run).
    per_source: {source_name: rows deleted} for fresh sources only.
    skipped_sources: sources skipped because their newest listing is older than
        the freshness window (likely a blocked adapter / dead worker).
    dry_run: whether anything was actually deleted.
    """

    deleted: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    skipped_sources: list[str] = field(default_factory=list)
    dry_run: bool = False


def _fresh_sources(session: Session, *, freshness_window_days: int) -> list[str]:
    """Sources whose newest listing was seen within the freshness window."""
    rows = session.execute(
        text("""
            SELECT source_name
              FROM watcher.listings
             GROUP BY source_name
            HAVING MAX(last_seen_at) >= now() - (:fw || ' days')::interval
        """),
        {"fw": freshness_window_days},
    ).scalars().all()
    return list(rows)


def _all_sources(session: Session) -> list[str]:
    rows = session.execute(
        text("SELECT DISTINCT source_name FROM watcher.listings")
    ).scalars().all()
    return list(rows)


def cleanse_stale(
    session: Session,
    *,
    older_than_days: int = DEFAULT_OLDER_THAN_DAYS,
    freshness_window_days: int = DEFAULT_FRESHNESS_WINDOW_DAYS,
    exempt_statuses: tuple[str, ...] = DEFAULT_EXEMPT_STATUSES,
    dry_run: bool = False,
) -> CleanseResult:
    """Delete listings unseen for `older_than_days`, per fresh source.

    A source is "fresh" if its newest listing was seen within
    `freshness_window_days`. Stale-but-not-fresh sources are skipped entirely so
    a crawler outage can't wipe live listings. Rows whose `listing_status` is in
    `exempt_statuses` (default: manual seeds) are never deleted.

    The caller owns the transaction: commit on success, rollback to discard.
    With `dry_run=True` nothing is deleted — counts reflect what would be.
    """
    fresh = set(_fresh_sources(session, freshness_window_days=freshness_window_days))
    skipped = sorted(s for s in _all_sources(session) if s not in fresh)
    result = CleanseResult(skipped_sources=skipped, dry_run=dry_run)

    if not fresh:
        logger.warning(
            "cleanse-listings: no source seen within %d day(s); skipping all "
            "(crawler may be down or every adapter blocked)",
            freshness_window_days,
        )
        return result

    exempt = list(exempt_statuses)
    params = {
        "sources": list(fresh),
        "d": older_than_days,
        "exempt": exempt,
    }

    if dry_run:
        rows = session.execute(
            text("""
                SELECT source_name, COUNT(*) AS n
                  FROM watcher.listings
                 WHERE source_name = ANY(:sources)
                   AND last_seen_at < now() - (:d || ' days')::interval
                   AND listing_status <> ALL(:exempt)
                 GROUP BY source_name
            """),
            params,
        ).mappings().all()
        result.per_source = {r["source_name"]: r["n"] for r in rows}
        result.deleted = sum(result.per_source.values())
        return result

    rows = session.execute(
        text("""
            DELETE FROM watcher.listings
             WHERE source_name = ANY(:sources)
               AND last_seen_at < now() - (:d || ' days')::interval
               AND listing_status <> ALL(:exempt)
            RETURNING source_name
        """),
        params,
    ).scalars().all()

    per_source: dict[str, int] = {}
    for src in rows:
        per_source[src] = per_source.get(src, 0) + 1
    result.per_source = per_source
    result.deleted = len(rows)
    return result
