# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo contains two independent sub-projects:

1. **`motorcycle_parts_watcher/`** — Python crawler and tracker for Suzuki Katana 1100 (1990) and Hayabusa 2003 parts listings.
2. **`console/`** — Laravel 12 / PHP 8.2 web frontend (Velzon admin template, Vite).

---

## Python Crawler (`motorcycle_parts_watcher`)

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in DATABASE_URL and EBAY_CLIENT_ID/SECRET
alembic upgrade head
parts-watch init-db
```

### Commands

```bash
# Tests
python3 -m pytest -q
python3 -m pytest tests/test_categorizer.py  # single test file

# Migrations
alembic upgrade head

# CLI
parts-watch crawl --bike katana1100
parts-watch crawl --bike hayabusa2003
parts-watch crawl-all
parts-watch report --format markdown
parts-watch report --format html
parts-watch export --format csv
parts-watch export --format json
```

### Architecture

Data flows: **Adapter → `NormalizedListing` → `IngestService` → PostgreSQL**

- **`adapters/`** — one file per source (`ebay.py` is primary; `yahoo_auctions.py`, `webike.py` are stubs; `manual_search.py` is fallback). All implement the `ListingAdapter` protocol from `adapters/base.py`: `name`, `enabled`, `async fetch(bike_key) -> list[NormalizedListing]`.
- **`schemas.py`** — `NormalizedListing` (Pydantic) is the contract between adapters and the ingestion layer.
- **`services/ingest.py`** — categorizes (via `utils/categorizer.py`), hashes (`utils/hashing.py`), deduplicates (unique on `source_name+source_item_id` and `url`), then upserts into `watcher.listings` and always appends a row to `watcher.listing_snapshots`.
- **`services/crawl.py`** — orchestrates adapters per bike, calls `IngestService`.
- **`services/reporting.py`** — queries DB, groups by bike/category/condition/source, renders `templates/report.html.j2` (Jinja2) or Markdown.
- **`models.py`** — SQLAlchemy ORM: `Bike`, `Source`, `Listing`, `ListingSnapshot` (all in `watcher` schema).
- **`cli.py`** — Typer app; entrypoint is the `parts-watch` script.

### Database

- PostgreSQL only (`postgresql+psycopg://`). SQLite is not supported.
- Schema: `watcher`. Tables: `bikes`, `sources`, `listings`, `listing_snapshots`.
- `listings` deduplication keys: `(source_name, source_item_id)` UNIQUE, `url` UNIQUE, `content_hash` index.
- `listing_snapshots` preserves price/availability history (one row per crawl per listing).
- Migrations managed by Alembic (`alembic/versions/`).

### Key Environment Variables

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher
EBAY_ENABLED=true
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_US
YAHOO_AUCTIONS_ENABLED=false
WEBIKE_ENABLED=false
MANUAL_SEARCH_ENABLED=true
HTTP_TIMEOUT_SECONDS=20
HTTP_RETRIES=3
HTTP_RATE_LIMIT_PER_SECOND=3
```

### Conventions

- Adapters: fetch and normalize only. No DB logic inside adapters.
- Dedup/storage: `services/ingest.py` exclusively.
- Type hints required on all public functions and service methods.
- `snake_case` for files/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.

---

## Laravel Console (`console/`)

```bash
cd console
composer install
npm install         # or: yarn
npm run dev         # Vite dev server
php artisan serve   # Laravel dev server

# Tests (Pest)
php artisan test
```

Built on Laravel 12 with Laravel UI and the Velzon admin template. Frontend assets use Vite.
