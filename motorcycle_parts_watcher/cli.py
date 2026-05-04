from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

from motorcycle_parts_watcher.bikes import load_bike_by_key
from motorcycle_parts_watcher.config import get_settings
from motorcycle_parts_watcher.db import SessionLocal
from motorcycle_parts_watcher.services.bootstrap import seed_sources
from motorcycle_parts_watcher.services.catalog_sync import sync_catalog
from motorcycle_parts_watcher.services.crawl import CrawlService
from motorcycle_parts_watcher.services.exporting import export_listings
from motorcycle_parts_watcher.services.migrations import run_migrations_to_head
from motorcycle_parts_watcher.services.reporting import generate_reports

app = typer.Typer(help="Motorcycle parts watcher CLI.")
console = Console()


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


@app.command("crawl")
def crawl(
    bike: Annotated[str, typer.Option(help="Catalog key, e.g. suzuki-katana-1100-1990")],
) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        if not load_bike_by_key(session, bike):
            raise typer.BadParameter(f"Unknown catalog_key: {bike}")
        service = CrawlService(session, settings)
        result = asyncio.run(service.crawl_bike(bike))
    console.print(
        f"[cyan]Crawled {bike}[/cyan] found={result.total_found} ingested={result.total_ingested} "
        f"sources={result.source_breakdown}"
    )


@app.command("crawl-all")
def crawl_all(
    skip_watches: Annotated[bool, typer.Option(help="Skip the watch-list re-crawl pass")] = False,
) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        service = CrawlService(session, settings)
        results = asyncio.run(service.crawl_all(include_watches=not skip_watches))
    if not results:
        console.print("[yellow]No active bikes — add bikes via the web UI's My Bike page.[/yellow]")
        return
    for row in results:
        tag = f" q={row.query!r}" if row.query else ""
        console.print(
            f"[cyan]{row.bike_key}[/cyan]{tag} found={row.total_found} ingested={row.total_ingested} "
            f"sources={row.source_breakdown}"
        )


@app.command("crawl-watches")
def crawl_watches() -> None:
    """Re-crawl only the high-priority watch entries (skip the bike sweep)."""
    settings = get_settings()
    with SessionLocal() as session:
        service = CrawlService(session, settings)
        results = asyncio.run(service.crawl_watches())
    if not results:
        console.print("[yellow]No active high-priority watches.[/yellow]")
        return
    for row in results:
        console.print(
            f"[cyan]{row.bike_key}[/cyan] q={row.query!r} found={row.total_found} "
            f"ingested={row.total_ingested} sources={row.source_breakdown}"
        )


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
) -> None:
    """Run an ad-hoc keyword search against the configured adapters."""
    settings = get_settings()
    with SessionLocal() as session:
        service = CrawlService(session, settings)
        if bike:
            results = []
            for key in bike:
                if not load_bike_by_key(session, key):
                    raise typer.BadParameter(f"Unknown catalog_key: {key}")
                results.append(asyncio.run(service.crawl_bike(key, query=query)))
        else:
            results = asyncio.run(service.crawl_all(query=query))

    for row in results:
        console.print(
            f"[cyan]{row.bike_key}[/cyan] q={query!r} found={row.total_found} "
            f"ingested={row.total_ingested} sources={row.source_breakdown}"
        )


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
