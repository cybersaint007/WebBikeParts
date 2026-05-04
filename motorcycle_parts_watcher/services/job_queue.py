"""Postgres-backed job queue for distributed crawl workers.

Producers (CrawlProducer) insert rows; workers claim via
SELECT ... FOR UPDATE SKIP LOCKED filtered by their adapter allowlist,
so multiple workers across hosts share one logical queue without double-running.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@dataclass
class Job:
    id: int
    bike_catalog_key: str
    adapter: str
    query: str | None
    original_query: str | None
    priority: int
    status: str
    attempts: int
    max_attempts: int
    watch_ids: list[int] | None
    enqueued_by: str | None


def enqueue(
    session: Session,
    *,
    adapter: str,
    bike_catalog_key: str,
    query: str | None = None,
    original_query: str | None = None,
    priority: int = 100,
    watch_ids: list[int] | None = None,
    enqueued_by: str | None = None,
) -> int | None:
    """Insert a job. Returns the new job id, or None if a duplicate in-flight
    row exists (uq_crawl_jobs_inflight partial unique blocks it)."""
    sql = text("""
        INSERT INTO watcher.crawl_jobs
              (bike_catalog_key, adapter, query, original_query,
               priority, watch_ids, enqueued_by)
        VALUES (:bike_catalog_key, :adapter, :query, :original_query,
                :priority, :watch_ids, :enqueued_by)
        ON CONFLICT DO NOTHING
        RETURNING id
    """)
    row = session.execute(
        sql,
        {
            "bike_catalog_key": bike_catalog_key,
            "adapter": adapter,
            "query": query,
            "original_query": original_query,
            "priority": priority,
            "watch_ids": watch_ids,
            "enqueued_by": enqueued_by,
        },
    ).first()
    return row[0] if row else None


def claim_next(
    session: Session,
    *,
    worker_id: str,
    adapters: list[str],
) -> Job | None:
    """Atomically claim one pending job whose adapter is in the worker's allowlist."""
    if not adapters:
        return None

    sql = text("""
        UPDATE watcher.crawl_jobs
           SET status = 'running',
               locked_by = :worker_id,
               locked_at = now(),
               started_at = COALESCE(started_at, now()),
               attempts = attempts + 1
         WHERE id = (
             SELECT id FROM watcher.crawl_jobs
              WHERE status = 'pending'
                AND adapter = ANY(:adapters)
              ORDER BY priority, id
              FOR UPDATE SKIP LOCKED
              LIMIT 1
         )
        RETURNING id, bike_catalog_key, adapter, query, original_query,
                  priority, status, attempts, max_attempts, watch_ids, enqueued_by
    """)
    row = session.execute(sql, {"worker_id": worker_id, "adapters": adapters}).mappings().first()
    if row is None:
        return None
    return Job(**dict(row))


def complete(session: Session, job_id: int, *, found: int, ingested: int) -> None:
    session.execute(
        text("""
            UPDATE watcher.crawl_jobs
               SET status = 'completed',
                   completed_at = now(),
                   locked_by = NULL,
                   locked_at = NULL,
                   last_error = NULL,
                   result_found = :found,
                   result_ingested = :ingested
             WHERE id = :id
        """),
        {"id": job_id, "found": found, "ingested": ingested},
    )


def fail(session: Session, job_id: int, *, error: str) -> str:
    """Mark failed. Re-queue as 'pending' if attempts < max_attempts; otherwise
    terminal 'failed'. Returns the resulting status."""
    row = session.execute(
        text("""
            UPDATE watcher.crawl_jobs
               SET status = CASE WHEN attempts < max_attempts
                                   THEN 'pending'
                                   ELSE 'failed' END,
                   locked_by = NULL,
                   locked_at = NULL,
                   last_error = :error,
                   completed_at = CASE WHEN attempts < max_attempts
                                          THEN NULL
                                          ELSE now() END
             WHERE id = :id
           RETURNING status
        """),
        {"id": job_id, "error": (error or "")[:8000]},
    ).first()
    return row[0] if row else "unknown"


def release_stale(session: Session, *, stale_after_minutes: int = 30) -> int:
    """Return rows stuck in 'running' (worker probably crashed) back to 'pending'."""
    result = session.execute(
        text("""
            UPDATE watcher.crawl_jobs
               SET status = 'pending',
                   locked_by = NULL,
                   locked_at = NULL,
                   last_error = COALESCE(last_error, '') || ' [released stale lock]'
             WHERE status = 'running'
               AND locked_at < now() - (:min || ' minutes')::interval
        """),
        {"min": stale_after_minutes},
    )
    return result.rowcount or 0


def pending_count(session: Session, adapter: str | None = None) -> int:
    if adapter:
        return session.execute(
            text("SELECT count(*) FROM watcher.crawl_jobs WHERE status='pending' AND adapter=:a"),
            {"a": adapter},
        ).scalar_one()
    return session.execute(
        text("SELECT count(*) FROM watcher.crawl_jobs WHERE status='pending'"),
    ).scalar_one()


def summary(session: Session) -> list[dict]:
    """Counts grouped by (status, adapter) for the `jobs` admin command."""
    rows = session.execute(
        text("""
            SELECT status, adapter, count(*) AS n
              FROM watcher.crawl_jobs
             GROUP BY status, adapter
             ORDER BY status, adapter
        """),
    ).mappings().all()
    return [dict(r) for r in rows]


def list_stuck(session: Session, *, stale_after_minutes: int = 30) -> list[dict]:
    rows = session.execute(
        text("""
            SELECT id, adapter, bike_catalog_key, query, locked_by, locked_at, attempts
              FROM watcher.crawl_jobs
             WHERE status = 'running'
               AND locked_at < now() - (:min || ' minutes')::interval
             ORDER BY locked_at
        """),
        {"min": stale_after_minutes},
    ).mappings().all()
    return [dict(r) for r in rows]


def jobs_for_bike(
    session: Session,
    bike_catalog_key: str,
    *,
    enqueued_by: str | None = None,
) -> list[dict]:
    """Used by the wait-loop in `parts-watch crawl --bike X` to poll for completion."""
    if enqueued_by is not None:
        rows = session.execute(
            text("""
                SELECT id, adapter, status, attempts, result_found, result_ingested, last_error
                  FROM watcher.crawl_jobs
                 WHERE bike_catalog_key = :k AND enqueued_by = :e
                 ORDER BY id
            """),
            {"k": bike_catalog_key, "e": enqueued_by},
        ).mappings().all()
    else:
        rows = session.execute(
            text("""
                SELECT id, adapter, status, attempts, result_found, result_ingested, last_error
                  FROM watcher.crawl_jobs
                 WHERE bike_catalog_key = :k
                 ORDER BY id
            """),
            {"k": bike_catalog_key},
        ).mappings().all()
    return [dict(r) for r in rows]


def jobs_for_enqueued_by(session: Session, enqueued_by: str) -> list[dict]:
    rows = session.execute(
        text("""
            SELECT id, adapter, bike_catalog_key, status, attempts,
                   result_found, result_ingested, last_error
              FROM watcher.crawl_jobs
             WHERE enqueued_by = :e
             ORDER BY id
        """),
        {"e": enqueued_by},
    ).mappings().all()
    return [dict(r) for r in rows]


def prune(session: Session, *, older_than_days: int = 7) -> int:
    """Delete completed/failed rows older than the cutoff. Returns rows deleted."""
    result = session.execute(
        text("""
            DELETE FROM watcher.crawl_jobs
             WHERE status IN ('completed', 'failed')
               AND completed_at < now() - (:d || ' days')::interval
        """),
        {"d": older_than_days},
    )
    return result.rowcount or 0
