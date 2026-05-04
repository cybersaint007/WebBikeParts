# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two sub-projects sharing one PostgreSQL database (`bike_parts_watcher`):

- **`motorcycle_parts_watcher/`** — Python 3.12+ async crawler. Pulls aftermarket / OEM / used parts listings from eBay and Webike (Yahoo Auctions stub) into the `watcher` schema. Typer CLI entrypoint: `parts-watch`.
- **`console/`** — Laravel 12 / PHP 8.2 web UI (Velzon admin template, Vite, Bootstrap 5). Owns the `console` schema, reads from `watcher` via a second DB connection, and **shells out to `parts-watch`** via queued jobs for on-demand crawls and catalog sync.

The two pieces are not independent — the console drives crawl scope (users pick bikes; only those get crawled) and triggers ad-hoc work.

---

## Python crawler — `motorcycle_parts_watcher/`

### Setup and commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # set DATABASE_URL + EBAY_* + WEBIKE_*
python3 -m alembic upgrade head      # creates watcher schema and tables
parts-watch init-db                  # seeds sources / bootstrap bikes

# Tests (pytest + pytest-asyncio)
python3 -m pytest -q
python3 -m pytest tests/test_categorizer.py::test_specific_case  # one test

# CLI
parts-watch sync-catalog                          # scrape webike Make→Model catalog into watcher.bike_catalog
parts-watch crawl --bike <catalog_key>            # one bike, e.g. suzuki-katana-1100-1990
parts-watch crawl-all                             # bike sweep + watch-list sweep (see below)
parts-watch crawl-all --skip-watches              # bike sweep only
parts-watch crawl-watches                         # watch-list sweep only
parts-watch search --query "exhaust" --bike-key suzuki-katana-1100-1990
parts-watch report --format markdown|html
parts-watch export --format csv|json
```

### Architecture

Data flow: **Adapter → `NormalizedListing` → `IngestService` → PostgreSQL `watcher.listings` (+ snapshot)**

- **`adapters/`** — one file per source. All implement `ListingAdapter` from `adapters/base.py`:
  `async fetch(bike: BikeRef, query: str | None = None) -> list[NormalizedListing]`.
  - `ebay.py` — primary, OAuth + Browse API
  - `webike.py` — scrapes the bike's `/md/{ID}` page; reads schema.org microdata (`<meta itemprop="price">`); finds product images by walking *up* from the price meta to a sibling `item__header__img` div
  - `manual_search.py` — fallback that hashes the query into `source_item_id` so different queries on the same bike produce distinct rows
  - `yahoo_auctions.py` — stub
- **`schemas.py`** — `NormalizedListing` (Pydantic) is the adapter↔ingest contract.
- **`bikes.py`** — `BikeRef` dataclass; `load_active_bikes(session)` returns the set of bikes any console user has selected (joins `console.user_bikes` cross-schema). The crawl scope is **DB-driven**, not hardcoded.
- **`services/ingest.py`** — categorizes (`utils/categorizer.py`), hashes (`utils/hashing.py`), upserts on `(source_name, source_item_id)` UNIQUE, always writes one `listing_snapshots` row per crawl.
- **`services/crawl.py`** — orchestrates two passes per `crawl-all`:
  1. **bike sweep** — every adapter against every active bike (no query)
  2. **watch sweep** — for each `is_high_priority=true` row in `console.parts_watches`, run adapters with the saved query; updates `last_crawled_at` and `match_count`
- **`services/catalog_sync.py`** — webike.tw scraper that populates `watcher.bike_catalog` and `watcher.categories`. Configured via `WEBIKE_CATALOG_MAKES`.
- **`utils/http.py`** — shared async client factory + `AsyncRateLimiter` + `with_retries`. Adapters must use this, not raw `httpx`.

### Conventions

- Adapters: fetch and normalize only. No DB writes.
- Dedup/storage: `services/ingest.py` exclusively.
- Type hints on all public functions. `snake_case` for files/functions, `PascalCase` for classes.
- `BikeRef.year_start == year_end == 0` means "year unknown" (common for webike-scraped catalog rows). `BikeRef.display_year` returns empty string in that case — adapters must strip resulting trailing whitespace from titles.
- The Webike `_find_product_container` walker stops at the *price* meta's nearest ancestor that contains a `/sd/` anchor (this is `item__body p-2`). The product image lives in a sibling, so `_best_image` walks up an additional level.

---

## Laravel console — `console/`

```bash
cd console
composer install
npm install && npm run dev          # Vite dev server (or: npm run build)
php artisan serve                   # Laravel dev server
php artisan test                    # Pest

# REQUIRED for any on-demand action (Refresh catalog, Live search, auto-crawl on bike add):
php artisan queue:work --queue=sync
```

### Architecture

- **Two DB connections** in `config/database.php`:
  - `pgsql` (default) — `console` schema; owns `users`, `user_bikes`, `parts_watches`, `sync_runs`
  - `pgsql_watcher` — `watcher` schema; read-only-ish; models under `App\Models\Watcher\*` set `protected $connection = 'pgsql_watcher'`
- **No DB-level FKs across schemas.** `user_bikes.bike_catalog_id` and `parts_watches.bike_catalog_id` are soft FKs validated at the app layer.
- **Auth**: registration disabled (`Auth::routes(['register' => false])`). Admin seeded by `AdminUserSeeder` from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Default: `admin@example.com` / `changeme123`.
- **Queued jobs** under `app/Jobs/` all shell out to `parts-watch`:
  - `SyncWebikeCatalogJob` — `parts-watch sync-catalog`
  - `CrawlBikeJob` — `parts-watch crawl --bike <catalog_key>`, dispatched from `MyBikesController@store` so a new bike has listings within minutes
  - `LiveSearchJob` — `parts-watch search --query <q> --bike-key …`
  - `RunPartsWatchJob` — base class with the env-override gotcha below
- **CRITICAL — subprocess env override**: when Laravel shells out, `Process::env([...])` must explicitly set `DATABASE_URL` and `DB_SCHEMA=watcher`. Otherwise the child process inherits Laravel's `DB_SCHEMA=console` and the crawler hits the wrong schema (e.g. `console.sources` doesn't exist). See `RunPartsWatchJob.php`.
- **Watch list semantics**: every `/parts/live-search` POST `firstOrCreate`s a `parts_watches` row at high priority (re-promotes if previously revoked). "Revoke priority" sets `is_high_priority=false` + `priority_revoked_at=now()` but **keeps the row**. Only the watch-sweep pass in `services/crawl.py` re-crawls high-priority rows.
- **Pagination**: `AppServiceProvider::boot()` calls `Paginator::useBootstrapFive()`. Velzon is Bootstrap 5 — without this, Laravel's default Tailwind paginator markup renders broken.
- **Routes**: any custom route must come **above** the catch-all `Route::get('{any}', ...)` in `routes/web.php` or it'll be swallowed.

### Key models

| Model | Connection | Notes |
|---|---|---|
| `App\Models\User` | `pgsql` | `userBikes()`, `partsWatches()`, helper `selectedCatalogBikeIds()` |
| `App\Models\UserBike` | `pgsql` | Soft FK to `Watcher\BikeCatalog` |
| `App\Models\PartsWatch` | `pgsql` | Watch-list row; `is_high_priority` drives re-crawl |
| `App\Models\SyncRun` | `pgsql` | Tracks queued/running jobs; `kind` = `catalog`/`crawl_bike`/`live_search` |
| `App\Models\Watcher\BikeCatalog` | `pgsql_watcher` | `displayLabel()`; `availableMakes()`, `modelsForMake()`, `yearsForModel()` for cascading dropdowns |
| `App\Models\Watcher\Listing` | `pgsql_watcher` | Scopes: `forBikeKeys`, `category`, `source`, `condition`, `priceBetween`, `search` (ILIKE on title/description/part_number/fitment_text) |

---

## Database

- **PostgreSQL only** (`postgresql+psycopg://`). No SQLite.
- One DB, two schemas: `watcher` (Python/Alembic) + `console` (Laravel migrations).
- Alembic migrations: `alembic/versions/` (`0001_initial_schema`, `0002_bike_catalog`, `0003_categories`, `0004_search_indexes` — `pg_trgm` GIN on `title`/`description`/`part_number`).
- Listings dedup: `(source_name, source_item_id)` UNIQUE, `url` UNIQUE, `content_hash` indexed.
- See `MOTORCYCLE_PARTS_WATCHER_DATABASE.md` for the full ER + sample queries (note: predates `bike_catalog` and `categories`).

### Key environment variables

Top-level `.env` (Python crawler):

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher
EBAY_ENABLED=true   EBAY_CLIENT_ID=…   EBAY_CLIENT_SECRET=…   EBAY_MARKETPLACE_ID=EBAY_US
WEBIKE_ENABLED=true   WEBIKE_CATALOG_MAKES=SUZUKI,HONDA,YAMAHA,KAWASAKI
MANUAL_SEARCH_ENABLED=true
HTTP_TIMEOUT_SECONDS=20   HTTP_RETRIES=3   HTTP_RATE_LIMIT_PER_SECOND=3
```

`console/.env` (Laravel) needs the same DB plus `DB_SCHEMA=console`, `WATCHER_DB_SCHEMA=watcher`, `ADMIN_EMAIL`/`ADMIN_PASSWORD`, and `QUEUE_CONNECTION=database`.
