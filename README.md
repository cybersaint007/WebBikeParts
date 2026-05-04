# Motorcycle Parts Watcher (PostgreSQL)

Crawler system for aftermarket, OEM, and used parts for:

- 1990 Suzuki Katana 1100 SL (GSX1100S / GS110X)
- 2003 Suzuki GSX1300R Hayabusa

This implementation is **PostgreSQL-only**. SQLite is not supported.

## Stack

- Python 3.12
- PostgreSQL
- SQLAlchemy + Alembic
- httpx (async)
- pydantic
- Typer + Rich
- Jinja2
- python-dotenv

## Quick Start

1. Create PostgreSQL database:
   - `bike_parts_watcher`
2. Configure environment:
   - `cp .env.example .env`
   - Update credentials in `.env`
3. Install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e .[dev]`
4. Run migrations:
   - `alembic upgrade head`
5. Initialize seed data:
   - `parts-watch init-db`

## Required Environment

`DATABASE_URL` must be PostgreSQL with psycopg driver. Example:

`DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/bike_parts_watcher`

Set target schema (defaults to `watcher`):

`DB_SCHEMA=watcher`

## CLI Commands

- `parts-watch init-db`
- `parts-watch crawl --bike katana1100`
- `parts-watch crawl --bike hayabusa2003`
- `parts-watch crawl-all`
- `parts-watch report --format markdown`
- `parts-watch report --format html`
- `parts-watch export --format csv`
- `parts-watch export --format json`

## Reports

Generated outputs:

- `reports/latest.md`
- `reports/latest.html`
- `reports/katana1100.md`
- `reports/hayabusa2003.md`

Grouping dimensions:

- bike
- category
- condition
- source

## Scheduling

Cron example:

`0 8 * * * parts-watch crawl-all && parts-watch report --format markdown`

OpenClaw task file:

- `openclaw/tasks/bike-parts-watcher.md`

## Notes

- eBay adapter is primary (official API style: OAuth + Browse search).
- Yahoo Auctions/Webike adapters are optional and controlled by env flags.
- Manual search adapter provides fallback query-based discovery.
