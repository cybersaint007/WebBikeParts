# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two sub-projects sharing one PostgreSQL database (`bike_parts_watcher`):

- **`motorcycle_parts_watcher/`** — Python 3.12+ async crawler. Pulls aftermarket / OEM / used parts listings from eBay, Webike TW (per-bike `/md/` scrape + Playwright `/search` keyword scrape), Yahoo Auctions (JP), Buyee, Monotaro, plus a manual-search fallback, into the `watcher` schema. Several JP sources (`webike_jp`, `croooober`, `mercari`, `rakuten`, `goobike`) are stubs blocked on geo / SPA / API-key issues — see `ADAPTERS.md`. Typer CLI entrypoint: `parts-watch`.
- **`console/`** — Laravel 12 / PHP 8.2 web UI (Velzon admin template, Vite, Bootstrap 5). Owns the `console` schema, reads from `watcher` via a second DB connection, and **shells out to `parts-watch`** via queued jobs for on-demand crawls and catalog sync.

The two pieces are not independent — the console drives crawl scope (users pick bikes; only those get crawled) and triggers ad-hoc work.

### Reference docs

- `README.md` — project overview, install steps, adapter status table, CLI cheat sheet. Start here for the big picture.
- `CRAWLER_ARCHITECTURE.md` — end-to-end crawler runtime: producer/worker/queue/ingest/adapters/Laravel bridge, plus an operational runbook.
- `ADAPTERS.md` — per-source HTTP/parse details and the status (live vs blocked) of each adapter.
- `MOTORCYCLE_PARTS_WATCHER_DATABASE.md` — DB ER diagram + sample queries (predates `bike_catalog` / `categories`).
- `DEPLOYMENT.md` — step-by-step production setup: system packages, Postgres, Nginx, systemd units for Laravel queue worker and crawler worker, scheduler cron, JP geo-worker setup.
- `AGENTS.md` — coding style, naming conventions, and commit/PR guidelines for AI coding agents.

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
parts-watch worker --worker-id central-1 --adapters ebay,buyee,webike,manual_search,old_bike_barn
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
  `async fetch(bike: BikeRef, query: str | None = None) -> list[NormalizedListing]`. See `ADAPTERS.md` for the full table of live vs blocked adapters with parse details.
- **`schemas.py`** — `NormalizedListing` (Pydantic) is the adapter↔ingest contract.
- **`bikes.py`** — `BikeRef` dataclass; `load_active_bikes(session)` returns the set of bikes any console user has selected (joins `console.user_bikes` cross-schema). The crawl scope is **DB-driven**, not hardcoded.
- **`services/ingest.py`** — categorizes (`utils/categorizer.py`), hashes (`utils/hashing.py`), upserts on `(source_name, source_item_id)` UNIQUE, always writes one `listing_snapshots` row per crawl.
- **`services/job_queue.py`** — Postgres-backed queue helpers. Claim path: `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`. Dedup: partial UNIQUE on `(adapter, bike_catalog_key, COALESCE(query,''))` while `status IN ('pending','running')`.
- **`services/crawl.py`** — split into:
  - `CrawlProducer` — `enqueue_for_bike` / `enqueue_all` / `enqueue_watches`. Translates the query *per adapter* via `utils/i18n.py` at enqueue time, so the worker is dumb about translation. The producer is the only side that imports the translation dictionary.
  - `CrawlWorker` — `run_once` / `run_forever`. Claims one job filtered by `--adapters` allowlist, runs the adapter, ingests results via `IngestService`, marks the job complete/failed. Periodically calls `release_stale` so a crashed worker's locked rows return to `pending`.
- **`services/catalog_sync.py`** — webike.tw scraper that populates `watcher.bike_catalog` and `watcher.categories`. Three-pass: (1) scrape the home page for `/mf/{MAKE}/` links to get the full maker list (14 as of 2026-05; `DEFAULT_MAKES` is the offline fallback) and union with `WEBIKE_CATALOG_EXTRA_MAKES` (comma/whitespace-separated, uppercased) to cover brands the homepage doesn't link (e.g. KTM, MV Agusta, Husqvarna); (2) walk `/mf/{MAKE}/{cc}` index pages to upsert one umbrella row per model with `year_start=year_end=0`; (3) for each umbrella, fetch its `/md/{id}` detail page and upsert one row per `年式 : YYYY ~ YYYY` year-range variant (open-ended `~ ` end-years default to the current year), also extracting the first CDN image URL into `image_url`. `BikeCatalog::yearsForModel` returns the umbrella's `0` only when no real variants exist. The maker list used to be hardcoded via `WEBIKE_CATALOG_MAKES`; that env var is no longer read (commit `3b5bafb`). `image_url` is only written when the detail page yields an image — existing non-null values are not cleared if the page yields nothing.
- **`utils/http.py`** — shared async client factory + `AsyncRateLimiter` + `with_retries`. Adapters must use this, not raw `httpx`.
- **`adapters/webike_search.py`** — Playwright/headless-Chromium driver for `webike.tw/search?q=…`. Returns the full keyword catalog (paginates up to `MAX_PAGES = 5`), not just the ~20-30 products on a single `/md/{ID}` model page. Uses `source_name = "webike_search"` (distinct from `webike`), so a product appearing in both scrapes generates two rows; the `url` UNIQUE constraint on `watcher.listings` prevents physical duplicates. **Cloudflare-blocked from data-center / VPS IPs** — without `WEBIKE_PROXY_URL` set to a residential proxy (`socks5://user:pass@host:port` or `http://…`) the adapter logs a one-line WARNING and returns `[]`. Requires Playwright + Chromium; the Chromium binary is preinstalled in `Dockerfile.crawler` via `playwright install chromium --with-deps`.
- **`adapters/old_bike_barn.py`** — Shopify storefront for vintage Japanese parts (oldbikebarn.com). Uses two public JSON endpoints: `/collections.json?limit=250&page=N` (paginated, ~1000 collections total) and `/collections/{handle}/products.json?limit=250&page=N`. No API key, no WAF games. Bike→handle resolution is title-regex over the collection list (e.g. `"Suzuki GS1100 Parts (1980–1983)"` → `(Suzuki, GS1100)`), with the parsed map cached in-process for 24h via a class-level `_CollectionIndex`. Year filtering is **deliberately permissive** — the adapter ingests every product in the matched collection regardless of per-product year shorthand (e.g. `"Suzuki 80-81 GS1100 Engine Gasket Set"`); fitment refinement happens search-side via the ILIKE on `fitment_text`. Lookup falls back from whole `BikeRef.model` to the first model token, so a webike-catalog row like `model="GSX1100S KATANA"` still finds OBB's `GSX1100S` collection. Multi-model `"CB350 & CL350"` collections are split into both keys at index time. Rate-limited to 1 rps regardless of `HTTP_RATE_LIMIT_PER_SECOND`.

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
php artisan test                    # PHPUnit (default Laravel scaffolding under tests/{Feature,Unit})

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
  - `CrawlBikeJob` — `parts-watch crawl --bike <catalog_key>`, dispatched from `MyBikesController@store`. Times out if no worker is running for the required adapters.
  - `LiveSearchJob` — `parts-watch search --query <q> --bike-key …`
  - `CrawlAllJob` — `parts-watch crawl-all`, dispatched **hourly** by the scheduler (`Console\Kernel::schedule`). Skipped if a previous `crawl_all` SyncRun is still queued/running, so a long sweep doesn't pile up duplicates.
  - `CrawlWatchesJob` — `parts-watch crawl-watches`, dispatched hourly under the same in-flight guard.
  - `RunPartsWatchJob` — base class with the env-override gotcha below
- **CRITICAL — subprocess env override**: when Laravel shells out, `Process::env([...])` must explicitly set `DATABASE_URL` and `DB_SCHEMA=watcher`. Otherwise the child process inherits Laravel's `DB_SCHEMA=console` and the crawler hits the wrong schema (e.g. `console.sources` doesn't exist). `RunPartsWatchJob` builds `DATABASE_URL` from `WATCHER_DB_USERNAME / WATCHER_DB_PASSWORD / WATCHER_DB_HOST / WATCHER_DB_PORT / WATCHER_DB_DATABASE` (each falling back to the corresponding `DB_*` if unset). See `RunPartsWatchJob.php`.
- **`SyncRun.output_excerpt` keeps only the last 4000 chars.** A SQLAlchemy bulk-insert traceback's bind-param dump can fill the buffer on its own and hide the exception class at the head. To recover the full traceback, rerun the same `parts-watch` command directly: `source .venv/bin/activate && parts-watch <cmd> 2>&1 | tee /tmp/<cmd>.log`.
- **Bike images**: `watcher.bike_catalog.image_url` (added in migration `0006_bike_catalog_image`) is written by two independent paths: (a) `catalog_sync.py` during the `/md/{id}` pass, and (b) `MyBikesController` via `refreshImage` (scrapes DuckDuckGo image search with a vqd token handshake) or `uploadImage` (stores the file under `public/bike-images/<catalog_key>-<timestamp>.<ext>` and saves a root-relative URL). Both update the `BikeCatalog` model on the `pgsql_watcher` connection. The image is never cleared by `catalog_sync` if the detail page yields nothing — only an explicit upload/refresh replaces it.
- **Watch list semantics**: every `/parts/live-search` POST `firstOrCreate`s a `parts_watches` row at high priority (re-promotes if previously revoked). "Revoke priority" sets `is_high_priority=false` + `priority_revoked_at=now()` but **keeps the row**. Only the watch-sweep pass in `services/crawl.py` re-crawls high-priority rows.
- **Pagination**: `AppServiceProvider::boot()` calls `Paginator::useBootstrapFive()`. Velzon is Bootstrap 5 — without this, Laravel's default Tailwind paginator markup renders broken.
- **Routes**: any custom route must come **above** the catch-all `Route::get('{any}', ...)` in `routes/web.php` or it'll be swallowed.
- **Velzon template baggage**: ~200 demo views ship under `resources/views/` (`apps-*`, `charts-*`, `ui-*`, `forms-*`, `dashboard-*`, etc.) and are reachable only via the `{any}` catch-all → `HomeController::index` (renders any blade whose filename matches). The app's nav never links to them. Don't translate, refactor, or test them. The views actually wired into routes are: `parts/*`, `my-bikes/index`, `watch-list/index`, `admin/users/*`, `admin/adapters/index`, `auth/*`, `layouts/*`, `components/breadcrumb`. The Velzon sidebar's lower demo menu uses `@lang('translation.*')` keys from `resources/lang/<locale>/translation.php` — separate from the JSON files used by the app.
- **Blade `@json([...])` parse trap**: when the array literal contains nested calls with their own arrays (e.g. `__('key', ['x' => 0])`), Blade's regex parser miscounts brackets and emits broken PHP → 500. Build the array in a `@php` block first, then pass the variable: `@json($foo)`.

### Internationalization (i18n)

- Three locales: `en` (fallback), `ja`, `zh-TW`. Whitelist lives at `config('app.available_locales')`.
- Translation strings live in `console/resources/lang/{en,ja,zh-TW}.json` — **not** `lang/` at the project root. Laravel's `langPath()` auto-detects to `resources/lang/` because Velzon ships that directory; writing JSON to `lang/` does nothing. Keys are the English source string; lookups via `__('Apply filters')`. Missing keys fall through to the key, so untranslated strings render as English.
- `app/Http/Middleware/Localization.php` runs in the `web` group and resolves the locale in this order: `?lang=` query → session → cookie → `App\Services\IpLocaleResolver` (ip-api.com country → JP=ja, TW/HK/MO=zh-TW, 24h cache, private/invalid IPs short-circuit) → fallback. The first valid hit is persisted to session + 1y cookie.
- Manual switching: topbar dropdown links to `index/{locale}` → `HomeController::lang($locale)`, which validates against the whitelist and persists session + cookie.
- For JS-side translations, emit a `@php $foo = [...]; @endphp` block above the `<script>` and inject via `const FOO_I18N = @json($foo);` (see the `@json` parse trap above).

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
- PostgreSQL runs in a Docker container named `postgresql` (image `postgres:latest`), bound to `127.0.0.1:5432` and `100.85.170.113:5432`. The host's `postgresql` systemd service is **not** used. Data is bind-mounted from `/home/dockeradmin/system_sites/postgresql/data` on the host.
- One DB, two schemas: `watcher` (Python/Alembic) + `console` (Laravel migrations).
- Alembic migrations: `alembic/versions/` (`0001_initial_schema`, `0002_bike_catalog`, `0003_categories`, `0004_search_indexes` — `pg_trgm` GIN on `title`/`description`/`part_number`, `0005_crawl_jobs` — distributed-worker queue table, `0006_bike_catalog_image` — nullable `image_url` on `bike_catalog`).
- Listings dedup: `(source_name, source_item_id)` UNIQUE, `url` UNIQUE, `content_hash` indexed.
- Queue dedup: partial UNIQUE on `watcher.crawl_jobs (adapter, bike_catalog_key, COALESCE(query,''))` while `status IN ('pending','running')`.
- See `MOTORCYCLE_PARTS_WATCHER_DATABASE.md` for the full ER + sample queries (note: predates `bike_catalog` and `categories`).

### Key environment variables

Top-level `.env` (Python crawler):

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher
EBAY_ENABLED=true   EBAY_CLIENT_ID=…   EBAY_CLIENT_SECRET=…   EBAY_MARKETPLACE_IDS=EBAY_US,EBAY_GB,EBAY_DE,EBAY_AU
WEBIKE_ENABLED=true
WEBIKE_SEARCH_ENABLED=false   # Playwright keyword scrape; needs WEBIKE_PROXY_URL from VPS/cloud
WEBIKE_PROXY_URL=             # residential proxy for Cloudflare bypass (socks5://user:pass@host:port)
YAHOO_AUCTIONS_ENABLED=true
BUYEE_ENABLED=true
MONOTARO_ENABLED=true
MANUAL_SEARCH_ENABLED=true
OLD_BIKE_BARN_ENABLED=true   # Shopify storefront for vintage Japanese parts; no API key
HTTP_TIMEOUT_SECONDS=20   HTTP_RETRIES=3   HTTP_RATE_LIMIT_PER_SECOND=3
```

`console/.env` (Laravel) needs the same DB plus `DB_SCHEMA=console`, `WATCHER_DB_SCHEMA=watcher`, the `WATCHER_DB_*` connection vars (`USERNAME` / `PASSWORD` / `HOST` / `PORT` / `DATABASE` — each falls back to `DB_*` if unset; required by `RunPartsWatchJob`'s subprocess env override), `ADMIN_EMAIL` / `ADMIN_PASSWORD`, and `QUEUE_CONNECTION=database`.

### Docker Compose runtime

`docker-compose.yml` is the production runtime. It defines six long-running services plus two one-shot migrators, all sharing an external `postgresql_pgnet` network (the same network the Postgres container lives on):

- `php-migrate` (one-shot) → `php artisan migrate --force`
- `crawler-migrate` (one-shot) → `python3 -m alembic upgrade head`
- `php` — Laravel PHP-FPM (depends on `php-migrate`)
- `nginx` — serves `console/public/` + the named `bike_images` volume on port `8080`
- `queue` — `php artisan queue:work --queue=sync --sleep=3 --tries=1 --timeout=1800`
- `scheduler` — `while true; php artisan schedule:run; sleep 60; done` (no host cron needed)
- `crawler` — `parts-watch worker --worker-id central-1 --adapters ebay,buyee,webike,manual_search,yahoo_auctions,monotaro,old_bike_barn`

Bring it up with `docker compose up -d --build`. The `bike_images` named volume is mounted into both `php` (at `public/bike-images/`) and `nginx` (at `/var/www/bike-images/`, served via an alias) so user uploads survive container rebuilds. The external `postgresql_pgnet` network must exist before `docker compose up` — it's the network that the host's `postgresql` container is attached to.

**Note — `webike_search` is not in the compose worker's allowlist.** The `crawler` service runs `--adapters ebay,buyee,webike,manual_search,yahoo_auctions,monotaro,old_bike_barn`, so even with `WEBIKE_SEARCH_ENABLED=true` the producer enqueues `webike_search` jobs that no worker claims. To enable: extend the allowlist in `docker-compose.yml`, or run a dedicated worker (typically on a host with a residential proxy / non-data-center IP).

**`Dockerfile.console` bundles `parts-watch` (commit 3b10398).** The PHP image installs the crawler into a venv at `/opt/parts-watch/` and exports `WATCHER_PARTS_WATCH_BIN=/opt/parts-watch/bin/parts-watch`, so the `queue` and `scheduler` containers can shell out via `RunPartsWatchJob`. Operational consequence: a change to the Python crawler (`pyproject.toml`, `motorcycle_parts_watcher/`) now also invalidates the PHP image — the conditional rebuild in CI/deploy already covers this, but PHP-only thinking can mislead estimates.

### CI and deploy

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **`python`** — spins up Postgres 16, runs `alembic upgrade head`, then `pytest -q`.
2. **`laravel`** — same Postgres, runs Alembic for the watcher schema, `php artisan migrate` for console, then `php artisan test`.
3. **`docker-build`** — builds both Dockerfiles using stub `.env` files.
4. **`deploy`** — on push to `main`, SSHes to the prod host with `appleboy/ssh-action`, `git pull`s, and **conditionally rebuilds**: if `git diff` shows changes to `Dockerfile.*`, `docker/`, `pyproject.toml`, `alembic/`, or `motorcycle_parts_watcher/`, runs `docker compose up -d --build`; otherwise just `docker compose restart php queue scheduler`. PHP-only changes therefore deploy without an image rebuild — but Python crawler changes do. Keep this in mind when estimating deploy time.

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
