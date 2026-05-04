# `motorcycle_parts_watcher` File Structure (Beginner Guide)

This guide explains what each file in `motorcycle_parts_watcher/` does.

## Folder Tree

```text
motorcycle_parts_watcher/
├── __init__.py
├── __main__.py
├── bikes.py
├── cli.py
├── config.py
├── constants.py
├── db.py
├── models.py
├── schemas.py
├── adapters/
│   ├── __init__.py
│   ├── base.py
│   ├── ebay.py
│   ├── manual_search.py
│   ├── webike.py
│   └── yahoo_auctions.py
├── services/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── crawl.py
│   ├── exporting.py
│   ├── ingest.py
│   ├── migrations.py
│   └── reporting.py
├── templates/
│   └── report.html.j2
└── utils/
    ├── __init__.py
    ├── categorizer.py
    ├── hashing.py
    ├── http.py
    └── similarity.py
```

## Top-Level Files

### `motorcycle_parts_watcher/__init__.py`
- Marks this folder as a Python package.
- Usually contains package-level metadata or is kept minimal.

### `motorcycle_parts_watcher/__main__.py`
- Lets you run the package directly with:
  - `python -m motorcycle_parts_watcher`
- It starts the CLI app.

### `motorcycle_parts_watcher/bikes.py`
- Builds a quick lookup dictionary of supported bikes (by key).
- Used by crawler/adapters to validate bike keys like `katana1100`.

### `motorcycle_parts_watcher/cli.py`
- Main command-line interface (Typer app).
- Defines commands such as:
  - `init-db`
  - `crawl`
  - `crawl-all`
  - `report`
  - `export`

### `motorcycle_parts_watcher/config.py`
- Loads settings from environment variables (`.env`).
- Validates config values (for example, PostgreSQL URL format).
- Central place for runtime configuration like API toggles and schema.

### `motorcycle_parts_watcher/constants.py`
- Stores constant values used across the app.
- Includes:
  - allowed part categories
  - predefined bike seed data

### `motorcycle_parts_watcher/db.py`
- Creates SQLAlchemy engine and session factory.
- Configures database connection behavior (including schema search path).
- Provides a helper to open/close DB sessions safely.

### `motorcycle_parts_watcher/models.py`
- SQLAlchemy ORM models (database table definitions):
  - `Bike`
  - `Source`
  - `Listing`
  - `ListingSnapshot`
- This file maps Python classes to PostgreSQL tables.

### `motorcycle_parts_watcher/schemas.py`
- Pydantic data models used for validated in-memory data.
- `NormalizedListing` is the standard format adapters must return.

## `adapters/` (Data Source Connectors)

### `motorcycle_parts_watcher/adapters/__init__.py`
- Exposes adapter classes in one place for easy imports.

### `motorcycle_parts_watcher/adapters/base.py`
- Defines the shared adapter protocol/interface.
- Every adapter should provide:
  - `name`
  - `enabled`
  - `fetch(bike_key)`

### `motorcycle_parts_watcher/adapters/ebay.py`
- Primary adapter.
- Connects to eBay API (OAuth + Browse search).
- Converts raw eBay responses into `NormalizedListing`.

### `motorcycle_parts_watcher/adapters/manual_search.py`
- Fallback adapter.
- Creates manual search seed listings (or loads local manual listings file).
- Useful when API sources are unavailable.

### `motorcycle_parts_watcher/adapters/webike.py`
- Optional adapter stub for Webike.
- Currently placeholder logic; returns empty list until integrated.

### `motorcycle_parts_watcher/adapters/yahoo_auctions.py`
- Optional adapter stub for Yahoo Auctions.
- Currently placeholder logic; returns empty list until integrated.

## `services/` (Business Logic Layer)

### `motorcycle_parts_watcher/services/__init__.py`
- Marks the `services` directory as a package.

### `motorcycle_parts_watcher/services/bootstrap.py`
- Seeds initial records into DB:
  - bikes
  - sources
- Used by `parts-watch init-db`.

### `motorcycle_parts_watcher/services/crawl.py`
- Orchestrates crawling across adapters.
- Runs fetch jobs, ingests results, and commits DB changes.
- Supports per-bike crawling and crawl-all.

### `motorcycle_parts_watcher/services/exporting.py`
- Exports listing data to:
  - CSV
  - JSON
- Writes files under `reports/`.

### `motorcycle_parts_watcher/services/ingest.py`
- Core ingestion pipeline:
  - categorize listing
  - compute content hash
  - deduplicate
  - insert/update listing
  - always create snapshot history row

### `motorcycle_parts_watcher/services/migrations.py`
- Small helper to run Alembic migrations programmatically.

### `motorcycle_parts_watcher/services/reporting.py`
- Builds Markdown/HTML reports from DB listings.
- Handles grouping by bike/category/condition/source.
- Writes report output files.

## `templates/` (Report Templates)

### `motorcycle_parts_watcher/templates/report.html.j2`
- Jinja2 HTML template used by reporting service.
- Turns grouped listing data into a readable HTML report.

## `utils/` (Shared Helper Functions)

### `motorcycle_parts_watcher/utils/__init__.py`
- Marks utilities directory as a package.

### `motorcycle_parts_watcher/utils/categorizer.py`
- Keyword-based category classifier for parts.
- Maps listing text to categories like `engine`, `brakes`, etc.

### `motorcycle_parts_watcher/utils/hashing.py`
- Generates stable content hashes for listings.
- Used in deduplication and change tracking.

### `motorcycle_parts_watcher/utils/http.py`
- HTTP helpers:
  - async rate limiter
  - retry with backoff
  - shared async HTTP client setup
  - numeric parsing helper

### `motorcycle_parts_watcher/utils/similarity.py`
- Title similarity scoring (string similarity).
- Used as one dedupe signal for near-duplicate listings.

