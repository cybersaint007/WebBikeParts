from __future__ import annotations

import asyncio
import time
import uuid
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from motorcycle_parts_watcher.bikes import load_bike_by_key
from motorcycle_parts_watcher.config import get_settings
from motorcycle_parts_watcher.db import SessionLocal
from motorcycle_parts_watcher.services import job_queue, listings
from motorcycle_parts_watcher.services.bootstrap import seed_sources
from motorcycle_parts_watcher.services.catalog_sync import sync_catalog
from motorcycle_parts_watcher.services.crawl import CrawlProducer, CrawlWorker, EnqueueSummary
from motorcycle_parts_watcher.services.exporting import export_listings
from motorcycle_parts_watcher.services.migrations import run_migrations_to_head
from motorcycle_parts_watcher.services.reporting import generate_reports

app = typer.Typer(help="Motorcycle parts watcher CLI.")
console = Console()


# ---------- helpers ---------------------------------------------------------

_TERMINAL = {"completed", "failed"}


def _print_enqueue_summary(label: str, summary) -> None:
    parts = [f"{name}={n}" for name, n in summary.by_adapter.items()]
    skipped = sum(summary.skipped.values())
    skip_note = f" skipped_dup={skipped}" if skipped else ""
    console.print(
        f"[cyan]{label}[/cyan] enqueued={summary.total_enqueued}{skip_note} "
        f"adapters={{{', '.join(parts)}}}"
    )


def _wait_for(enqueued_by: str, *, timeout_seconds: int = 1500) -> list[dict]:
    """Poll watcher.crawl_jobs until every job tagged with `enqueued_by` reaches
    a terminal state, or timeout. Returns the final job rows."""
    deadline = time.monotonic() + timeout_seconds
    last_pending = -1
    while True:
        with SessionLocal() as session:
            rows = job_queue.jobs_for_enqueued_by(session, enqueued_by)
        if not rows:
            time.sleep(2)
            continue
        if all(r["status"] in _TERMINAL for r in rows):
            return rows
        pending = sum(1 for r in rows if r["status"] not in _TERMINAL)
        if pending != last_pending:
            console.print(f"[dim]waiting on {pending}/{len(rows)} jobs…[/dim]")
            last_pending = pending
        if time.monotonic() > deadline:
            console.print(
                f"[yellow]timeout: {pending} job(s) still not terminal after "
                f"{timeout_seconds}s[/yellow]"
            )
            return rows
        time.sleep(3)


def _print_job_results(rows: list[dict]) -> None:
    if not rows:
        return
    total_found = sum(r["result_found"] or 0 for r in rows)
    total_ingested = sum(r["result_ingested"] or 0 for r in rows)
    failed = [r for r in rows if r["status"] == "failed"]
    completed = [r for r in rows if r["status"] == "completed"]
    console.print(
        f"[green]done[/green] completed={len(completed)} failed={len(failed)} "
        f"found={total_found} ingested={total_ingested}"
    )
    for r in failed:
        console.print(
            f"  [red]failed[/red] {r['adapter']} #{r['id']}: "
            f"{(r.get('last_error') or '').splitlines()[0][:200]}"
        )


# ---------- one-shot setup --------------------------------------------------


@app.command("init-db")
def init_db() -> None:
    settings = get_settings()
    run_migrations_to_head()
    with SessionLocal() as session:
        seed_sources(session, settings)
        session.commit()
    console.print("[green]Database initialized and seed data applied.[/green]")


@app.command("sync-catalog")
def sync_catalog_cmd() -> None:
    """Scrape webike.tw to refresh watcher.bike_catalog and watcher.categories."""
    settings = get_settings()
    with SessionLocal() as session:
        stats = asyncio.run(sync_catalog(session, settings))
    console.print(
        f"[green]Catalog sync complete[/green]: bikes_upserted={stats.bikes_upserted} "
        f"categories_upserted={stats.categories_upserted} fetch_errors={stats.fetch_errors}"
    )


# ---------- producer-side commands (enqueue) --------------------------------


@app.command("crawl")
def crawl(
    bike: Annotated[str, typer.Option(help="Catalog key, e.g. suzuki-katana-1100-1990")],
    no_wait: Annotated[bool, typer.Option("--no-wait", help="Return immediately after enqueue")] = False,
    timeout: Annotated[int, typer.Option(help="Seconds to wait for all jobs to terminate")] = 1500,
) -> None:
    """Enqueue crawl jobs (one per enabled adapter) for a bike, then wait for completion."""
    settings = get_settings()
    tag = f"crawl:{bike}:{uuid.uuid4().hex[:8]}"
    with SessionLocal() as session:
        if not load_bike_by_key(session, bike):
            raise typer.BadParameter(f"Unknown catalog_key: {bike}")
        producer = CrawlProducer(session, settings)
        summary = producer.enqueue_for_bike(bike, enqueued_by=tag)
    _print_enqueue_summary(bike, summary)
    if no_wait or summary.total_enqueued == 0:
        return
    rows = _wait_for(tag, timeout_seconds=timeout)
    _print_job_results(rows)


@app.command("crawl-all")
def crawl_all(
    skip_watches: Annotated[bool, typer.Option(help="Skip the watch-list re-crawl pass")] = False,
) -> None:
    """Enqueue jobs for every active bike (and every high-priority watch). Returns immediately."""
    settings = get_settings()
    with SessionLocal() as session:
        producer = CrawlProducer(session, settings)
        summary = producer.enqueue_all(
            include_watches=not skip_watches, enqueued_by="crawl-all",
        )
    if summary.total_enqueued == 0:
        console.print("[yellow]No jobs enqueued — add bikes via the web UI's My Bike page.[/yellow]")
        return
    _print_enqueue_summary("crawl-all", summary)


@app.command("crawl-watches")
def crawl_watches() -> None:
    """Enqueue jobs only for the high-priority watch entries."""
    settings = get_settings()
    with SessionLocal() as session:
        producer = CrawlProducer(session, settings)
        summary = producer.enqueue_watches(enqueued_by="crawl-watches")
    if summary.total_enqueued == 0:
        console.print("[yellow]No active high-priority watches.[/yellow]")
        return
    _print_enqueue_summary("crawl-watches", summary)


@app.command("search")
def search(
    query: Annotated[str, typer.Option(help="Free-form search term to inject into adapter queries")],
    bike: Annotated[
        list[str] | None,
        typer.Option(
            "--bike-key", "--bike",
            help="Catalog key (repeatable). Omit to fan out to every active bike.",
        ),
    ] = None,
    no_wait: Annotated[bool, typer.Option("--no-wait", help="Return immediately after enqueue")] = False,
    timeout: Annotated[int, typer.Option(help="Seconds to wait for all jobs to terminate")] = 1500,
) -> None:
    """Enqueue an ad-hoc keyword search and (by default) wait for results."""
    settings = get_settings()
    tag = f"live-search:{uuid.uuid4().hex[:8]}"
    with SessionLocal() as session:
        producer = CrawlProducer(session, settings)
        if bike:
            for key in bike:
                if not load_bike_by_key(session, key):
                    raise typer.BadParameter(f"Unknown catalog_key: {key}")
            summary = EnqueueSummary()
            for key in bike:
                summary.merge(producer.enqueue_for_bike(key, query=query, enqueued_by=tag))
        else:
            summary = producer.enqueue_all(query=query, enqueued_by=tag)
    _print_enqueue_summary(f"search q={query!r}", summary)
    if no_wait or summary.total_enqueued == 0:
        return
    rows = _wait_for(tag, timeout_seconds=timeout)
    _print_job_results(rows)


# ---------- worker ----------------------------------------------------------


@app.command("worker")
def worker(
    worker_id: Annotated[str, typer.Option(help="Stable id, e.g. jp-1, central-1")],
    adapters: Annotated[
        str,
        typer.Option(help="Comma-separated adapter names this worker handles, e.g. webike_jp,yahoo_auctions"),
    ],
    poll_seconds: Annotated[int, typer.Option(help="Idle poll interval")] = 5,
    once: Annotated[bool, typer.Option("--once", help="Process at most one job and exit")] = False,
) -> None:
    """Long-lived worker. Claims jobs filtered by adapter allowlist, runs the adapter, ingests."""
    settings = get_settings()
    allowlist = [a.strip() for a in adapters.split(",") if a.strip()]
    if not allowlist:
        raise typer.BadParameter("--adapters must list at least one adapter name")
    w = CrawlWorker(
        session_factory=lambda: SessionLocal(),
        settings=settings,
        worker_id=worker_id,
        adapters=allowlist,
    )
    console.print(
        f"[green]worker[/green] {worker_id} adapters={allowlist} poll={poll_seconds}s"
    )
    if once:
        had_work = asyncio.run(w.run_once())
        console.print("processed 1 job" if had_work else "queue empty for our adapters")
        return
    try:
        asyncio.run(w.run_forever(poll_seconds=poll_seconds))
    except KeyboardInterrupt:
        console.print("[yellow]worker stopped[/yellow]")


# ---------- jobs admin ------------------------------------------------------


@app.command("jobs")
def jobs(
    stuck: Annotated[bool, typer.Option("--stuck", help="Show running jobs with stale locks")] = False,
    prune: Annotated[bool, typer.Option("--prune", help="Delete completed/failed rows older than --older-than-days")] = False,
    older_than_days: Annotated[int, typer.Option(help="Used with --prune")] = 7,
    release_stale_minutes: Annotated[int, typer.Option(help="Stale-lock cutoff for --stuck and --release-stale")] = 30,
    release_stale: Annotated[bool, typer.Option("--release-stale", help="Return stale-locked rows to pending")] = False,
) -> None:
    """Inspect / maintain the crawl_jobs queue."""
    with SessionLocal() as session:
        if prune:
            n = job_queue.prune(session, older_than_days=older_than_days)
            session.commit()
            console.print(f"[green]pruned[/green] {n} row(s) older than {older_than_days} day(s)")
            return
        if release_stale:
            n = job_queue.release_stale(session, stale_after_minutes=release_stale_minutes)
            session.commit()
            console.print(f"[green]released[/green] {n} stale-locked job(s)")
            return
        if stuck:
            rows = job_queue.list_stuck(session, stale_after_minutes=release_stale_minutes)
            if not rows:
                console.print(f"[green]no jobs running longer than {release_stale_minutes} min[/green]")
                return
            table = Table(title="stuck jobs")
            for col in ("id", "adapter", "bike_catalog_key", "query", "locked_by", "locked_at", "attempts"):
                table.add_column(col)
            for r in rows:
                table.add_row(*[str(r.get(c) or "") for c in
                                ("id", "adapter", "bike_catalog_key", "query",
                                 "locked_by", "locked_at", "attempts")])
            console.print(table)
            return

        rows = job_queue.summary(session)
    if not rows:
        console.print("[yellow]queue is empty[/yellow]")
        return
    table = Table(title="crawl_jobs by status × adapter")
    table.add_column("status"); table.add_column("adapter"); table.add_column("count", justify="right")
    for r in rows:
        table.add_row(r["status"], r["adapter"], str(r["n"]))
    console.print(table)


@app.command("cleanse-listings")
def cleanse_listings(
    older_than_days: Annotated[int, typer.Option(help="Delete listings unseen for N days")] = listings.DEFAULT_OLDER_THAN_DAYS,
    freshness_window_days: Annotated[int, typer.Option(help="Only delete from sources crawled within N days")] = listings.DEFAULT_FRESHNESS_WINDOW_DAYS,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report what would be deleted, delete nothing")] = False,
) -> None:
    """Hard-delete stale listings (unseen for N days), per fresh source."""
    with SessionLocal() as session:
        result = listings.cleanse_stale(
            session,
            older_than_days=older_than_days,
            freshness_window_days=freshness_window_days,
            dry_run=dry_run,
        )
        if not dry_run:
            session.commit()

    verb = "would delete" if dry_run else "deleted"
    console.print(
        f"[green]{verb}[/green] {result.deleted} listing(s) unseen for "
        f">{older_than_days} day(s)"
    )
    if result.per_source:
        table = Table(title=f"{verb} by source")
        table.add_column("source"); table.add_column("count", justify="right")
        for src, n in sorted(result.per_source.items()):
            table.add_row(src, str(n))
        console.print(table)
    if result.skipped_sources:
        console.print(
            f"[yellow]skipped[/yellow] (no listing seen within "
            f"{freshness_window_days} day(s) — adapter blocked or worker down): "
            f"{', '.join(result.skipped_sources)}"
        )


# ---------- reports / export ------------------------------------------------


@app.command("report")
def report(fmt: Annotated[str, typer.Option("--format", help="markdown or html")]) -> None:
    if fmt not in {"markdown", "html"}:
        raise typer.BadParameter("format must be markdown or html")
    with SessionLocal() as session:
        generate_reports(session, fmt)
    console.print(f"[green]Generated reports/latest.{fmt}[/green]")


@app.command("export")
def export(fmt: Annotated[str, typer.Option("--format", help="csv or json")]) -> None:
    if fmt not in {"csv", "json"}:
        raise typer.BadParameter("format must be csv or json")
    with SessionLocal() as session:
        out = export_listings(session, fmt)
    console.print(f"[green]Exported to {out}[/green]")


if __name__ == "__main__":
    app()
