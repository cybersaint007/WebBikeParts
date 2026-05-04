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

# CLI — producer side (enqueue into watcher.crawl_jobs)
parts-watch sync-catalog                          # scrape webike Make→Model catalog into watcher.bike_catalog
parts-watch crawl --bike <catalog_key>            # enqueue one bike's adapter jobs, then poll until done
parts-watch crawl --bike <catalog_key> --no-wait  # fire-and-forget
parts-watch crawl-all                             # enqueue bike sweep + watch sweep (returns immediately)
parts-watch crawl-all --skip-watches              # bike sweep only
parts-watch crawl-watches                         # watch sweep only
parts-watch search --query "exhaust" --bike-key suzuki-katana-1100-1990   # enqueues + waits

# CLI — worker side (claims and runs jobs)
parts-watch worker --worker-id central-1 --adapters ebay,buyee,webike,manual_search
parts-watch worker --worker-id jp-1 --adapters webike_jp,yahoo_auctions,croooober,mercari,monotaro,rakuten,goobike

# CLI — queue admin
parts-watch jobs                                  # counts by (status × adapter)
parts-watch jobs --stuck                          # rows in 'running' with stale lock
parts-watch jobs --release-stale                  # return stale-locked rows to pending
parts-watch jobs --prune --older-than-days 7      # delete completed/failed older than N days

parts-watch report --format markdown|html
parts-watch export --format csv|json
```

### Architecture

Data flow:
**`CrawlProducer` enqueues → `watcher.crawl_jobs` → `CrawlWorker` (one per host) claims → Adapter → `NormalizedListing` → `IngestService` → `watcher.listings`**

The producer and worker are decoupled by the queue so workers can run on geo-distributed hosts (a JP-locale worker for `webike_jp` / `yahoo_auctions` / `croooober` / `mercari` / `monotaro` / `rakuten` / `goobike`; a central worker for `ebay` / `webike` / `manual_search`). Workers connect to the central Postgres over a private link (WireGuard/Tailscale).

- **`adapters/`** — one file per source. All implement `ListingAdapter` from `adapters/base.py`:
  `async fetch(bike: BikeRef, query: str | None = None) -> list[NormalizedListing]`.
  - `ebay.py` — primary, OAuth + Browse API
  - `webike.py` — scrapes the bike's `/md/{ID}` page; reads schema.org microdata (`<meta itemprop="price">`); finds product images by walking *up* from the price meta to a sibling `item__header__img` div
  - `manual_search.py` — fallback that hashes the query into `source_item_id` so different queries on the same bike produce distinct rows
  - `yahoo_auctions.py` — direct scrape of auctions.yahoo.co.jp (works from JP IPs)
  - `buyee.py` — same Yahoo Auctions inventory via the buyee.jp proxy-buying service; reachable from non-JP IPs, English chrome, JPY prices preserved. `source_name="buyee"` so rows don't collide with `yahoo_auctions`.
- **`schemas.py`** — `NormalizedListing` (Pydantic) is the adapter↔ingest contract.
- **`bikes.py`** — `BikeRef` dataclass; `load_active_bikes(session)` returns the set of bikes any console user has selected (joins `console.user_bikes` cross-schema). The crawl scope is **DB-driven**, not hardcoded.
- **`services/ingest.py`** — categorizes (`utils/categorizer.py`), hashes (`utils/hashing.py`), upserts on `(source_name, source_item_id)` UNIQUE, always writes one `listing_snapshots` row per crawl.
- **`services/job_queue.py`** — Postgres-backed queue helpers. Claim path: `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`. Dedup: partial UNIQUE on `(adapter, bike_catalog_key, COALESCE(query,''))` while `status IN ('pending','running')`.
- **`services/crawl.py`** — split into:
  - `CrawlProducer` — `enqueue_for_bike` / `enqueue_all` / `enqueue_watches`. Translates the query *per adapter* via `utils/i18n.py` at enqueue time, so the worker is dumb about translation. The producer is the only side that imports the translation dictionary.
  - `CrawlWorker` — `run_once` / `run_forever`. Claims one job filtered by `--adapters` allowlist, runs the adapter, ingests results via `IngestService`, marks the job complete/failed. Periodically calls `release_stale` so a crashed worker's locked rows return to `pending`.
- **`services/catalog_sync.py`** — webike.tw scraper that populates `watcher.bike_catalog` and `watcher.categories`. Configured via `WEBIKE_CATALOG_MAKES`.
- **`utils/http.py`** — shared async client factory + `AsyncRateLimiter` + `with_retries`. Adapters must use this, not raw `httpx`.

### Queue conventions

- One job row per (bike, adapter, query) tuple. The producer emits *N bikes × M enabled adapters* rows per sweep.
- Priorities (lower = sooner): `25` live search, `50` watch sweep, `100` bike sweep.
- `enqueued_by` — opaque tag the CLI uses to follow a particular invocation: `"crawl:<bike>:<id>"`, `"live-search:<id>"`, `"crawl-all"`, `"crawl-watches"`. The CLI's wait-loop (`parts-watch crawl --bike X` / `parts-watch search`) polls `jobs_for_enqueued_by(tag)` until every row is terminal.
- `console.parts_watches.match_count` is **additive across per-adapter completions**, not per-sweep — every watch-job completion runs `match_count = match_count + :ingested_in_this_job`. Pre-queue, it was overwritten with the sweep total; the new semantic is "lifetime ingested for this watch."
- Adapters whose `Source` row is `enabled=false` are skipped at enqueue time (existing behaviour preserved). A worker that handles an adapter gets nothing if no producer is enqueueing for it.
- A worker connects to the central Postgres for: claim job → look up `BikeRef` → ingest listings → mark complete. Only the adapter's outbound HTTP request leaves the worker host. That's where geo-routing matters.

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

# REQUIRED for any on-demand action (Refresh catalog, Live search, auto-crawl on bike add)
# AND for the hourly scheduled sweeps to actually fire:
php artisan queue:work --queue=sync

# Required for the hourly sweeps. One cron entry runs the scheduler each minute;
# the scheduler decides which jobs are due. Without this, crawl-all / crawl-watches
# never run automatically.
* * * * * cd /path/to/console && php artisan schedule:run >> /dev/null 2>&1
```

### Architecture

- **Two DB connections** in `config/database.php`:
  - `pgsql` (default) — `console` schema; owns `users`, `user_bikes`, `parts_watches`, `sync_runs`
  - `pgsql_watcher` — `watcher` schema; read-only-ish; models under `App\Models\Watcher\*` set `protected $connection = 'pgsql_watcher'`
- **No DB-level FKs across schemas.** `user_bikes.bike_catalog_id` and `parts_watches.bike_catalog_id` are soft FKs validated at the app layer.
- **Auth**: registration disabled (`Auth::routes(['register' => false])`). Admin seeded by `AdminUserSeeder` from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Default: `admin@example.com` / `changeme123`.
- **Queued jobs** under `app/Jobs/` all shell out to `parts-watch`. The CLI now *enqueues* into `watcher.crawl_jobs` and (for `crawl` / `search`) blocks until the queued jobs hit a terminal state, so Laravel's `SyncRun` semantics are preserved:
  - `SyncWebikeCatalogJob` — `parts-watch sync-catalog` (unchanged)
  - `CrawlBikeJob` — `parts-watch crawl --bike <catalog_key>`, dispatched from `MyBikesController@store`. Will time out if no worker is running for the required adapters.
  - `LiveSearchJob` — `parts-watch search --query <q> --bike-key …`
  - `CrawlAllJob` — `parts-watch crawl-all`, dispatched **hourly** by the scheduler (`Console\Kernel::schedule`). Skipped if a previous `crawl_all` SyncRun is still queued/running, so a long sweep doesn't pile up duplicates.
  - `CrawlWatchesJob` — `parts-watch crawl-watches`, dispatched hourly under the same in-flight guard.
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
- Alembic migrations: `alembic/versions/` (`0001_initial_schema`, `0002_bike_catalog`, `0003_categories`, `0004_search_indexes` — `pg_trgm` GIN on `title`/`description`/`part_number`, `0005_crawl_jobs` — distributed-worker queue table).
- Listings dedup: `(source_name, source_item_id)` UNIQUE, `url` UNIQUE, `content_hash` indexed.
- Queue dedup: partial UNIQUE on `watcher.crawl_jobs (adapter, bike_catalog_key, COALESCE(query,''))` while `status IN ('pending','running')`.
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

### Distributed worker deployment

For geo-routing (e.g. JP-locale scrapers from a JP host to avoid IP blocks):

1. Spin up a remote host. Open a private network link to the central Postgres (WireGuard/Tailscale recommended; do **not** expose Postgres to the public internet).
2. Install the crawler: clone the repo, `pip install -e ".[dev]"`, copy the `.env` and override `DATABASE_URL` to point at the central DB over the private link.
3. Run a worker scoped to the adapters that should run from that locale:
   ```bash
   parts-watch worker --worker-id jp-1 --adapters webike_jp,yahoo_auctions,croooober,mercari,monotaro,rakuten,goobike
   ```
4. On the central host run a worker for the rest:
   ```bash
   parts-watch worker --worker-id central-1 --adapters ebay,buyee,webike,manual_search
   ```
5. Run both as systemd units. The worker periodically calls `release_stale` so a crashed worker's locked rows return to `pending`.

Operational notes:
- Translation runs at producer time on the central host, so the JP worker doesn't import the parts dictionary.
- A worker only fetches `BikeRef` metadata once per claim (single SELECT); the heavy outbound HTTP is the adapter scrape.
- `parts-watch jobs` gives a quick health view; `parts-watch jobs --stuck` surfaces rows whose worker died mid-run.
