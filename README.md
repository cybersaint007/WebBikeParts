# Motorcycle Parts Watcher

A two-part system that crawls aftermarket and OEM motorcycle parts listings from multiple sources and presents them in a web dashboard. Pick your bikes, save searches as watches, and let the crawler keep the listings fresh automatically.

## Overview

The project is split into two sub-projects that share one PostgreSQL database:

| Sub-project | Stack | Role |
|---|---|---|
| `motorcycle_parts_watcher/` | Python 3.12+, SQLAlchemy, Typer | Async crawler — fetches and ingests listings |
| `console/` | Laravel 12, PHP 8.2, Bootstrap 5 | Web UI — browse listings, manage bikes and watches |

The web console drives crawl scope (only bikes a user has selected get crawled) and triggers on-demand work by shelling out to the Python CLI. Workers can run on geographically distributed hosts connected to a central Postgres over a private network link.

## Features

- **Multi-source crawling** — eBay (multi-marketplace), Yahoo Auctions JP, Buyee, Webike TW, Monotaro, with stub scaffolding for Webike JP, Croooober, Mercari, Rakuten, and Goobike
- **Distributed worker queue** — Postgres-backed job queue with `FOR UPDATE SKIP LOCKED`; workers run in different regions for geo-restricted sources
- **Automatic deduplication** — four-tier dedup (`source_item_id`, URL, title similarity, content hash) across all sources
- **Price history** — every crawl appends a snapshot row so you can track how prices change over time
- **Watch list** — save a search query and have it re-crawled on every sweep; see lifetime match counts
- **Live search** — trigger an ad-hoc search from the UI; results appear within minutes
- **Query translation** — user queries are translated per-adapter (EN → JA for Yahoo/Monotaro, EN → ZH-TW for Webike) at enqueue time
- **Bike catalog sync** — auto-discovers all makes and model year-ranges from webike.tw; populates cascading dropdowns in the UI
- **Bike card images** — each bike card supports web image search (DuckDuckGo) or a user-uploaded photo
- **Three UI locales** — English, Japanese, Traditional Chinese; auto-detected from IP or switchable manually

## Architecture

```
┌──────────────┐        ┌────────────────────────────────┐        ┌──────────────────┐
│  Laravel UI  │──────► │   PostgreSQL: bike_parts_watcher│ ◄──────│  parts-watch     │
│  (console/)  │        │   console.*   |   watcher.*     │        │  worker          │
│              │        │   users       |   bike_catalog  │        │  --adapters …    │
│  queue:work  │        │   user_bikes  |   listings      │        │                  │
│      │       │        │   sync_runs   |   crawl_jobs    │        │  HTTP fetches to │
│      ▼       │        └────────────────────────────────┘        │  source sites    │
│  parts-watch │                                                    └──────────────────┘
│  crawl / sync│
└──────────────┘
```

The Laravel console dispatches queued jobs that shell out to `parts-watch`. The CLI enqueues jobs into `watcher.crawl_jobs`; one or more workers claim and execute them. Workers only need outbound HTTP to the source sites and a private link to Postgres — they never talk to the Laravel app directly.

For detailed runtime documentation see [`CRAWLER_ARCHITECTURE.md`](CRAWLER_ARCHITECTURE.md). For per-adapter HTML/API details see [`ADAPTERS.md`](ADAPTERS.md).

## Prerequisites

- PostgreSQL 15+
- Python 3.12+
- PHP 8.2+, Composer
- Node.js 20+ (for Vite asset compilation)

## Installation

### 1. Database

```bash
createdb bike_parts_watcher
```

### 2. Python crawler

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env              # fill in DATABASE_URL and source credentials
python3 -m alembic upgrade head   # creates watcher.* schema and tables
parts-watch init-db               # seeds watcher.sources
parts-watch sync-catalog          # populates watcher.bike_catalog from webike.tw (~20 min)
```

### 3. Laravel console

```bash
cd console
cp .env.example .env              # fill in DB_*, WATCHER_DB_*, ADMIN_EMAIL, ADMIN_PASSWORD
composer install
npm install && npm run build
php artisan migrate               # creates console.* schema
php artisan db:seed               # seeds the admin user
```

The admin account defaults to `admin@example.com` / `changeme123` — override via `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `console/.env` before seeding.

## Running

All four processes need to be running for the full system to work:

```bash
# Terminal 1 — Laravel dev server
cd console && php artisan serve

# Terminal 2 — Queue worker (required for on-demand crawls and scheduled sweeps)
cd console && php artisan queue:work --queue=sync

# Terminal 3 — Crawler worker
source .venv/bin/activate
parts-watch worker --worker-id local-1 \
  --adapters ebay,buyee,webike,manual_search,yahoo_auctions,monotaro

# Cron — hourly sweeps (add to crontab)
* * * * * cd /path/to/console && php artisan schedule:run >> /dev/null 2>&1
```

Open `http://localhost:8000`, log in, and add a bike. The crawler fires automatically when a bike is first added.

## Configuration

### Python crawler (`.env`)

```env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher

# eBay (free developer credentials from developer.ebay.com)
EBAY_ENABLED=true
EBAY_CLIENT_ID=your_app_id
EBAY_CLIENT_SECRET=your_cert_id
EBAY_MARKETPLACE_IDS=EBAY_US,EBAY_GB,EBAY_DE,EBAY_AU

# Other live sources (no credentials required)
YAHOO_AUCTIONS_ENABLED=true
BUYEE_ENABLED=true
WEBIKE_ENABLED=true
MONOTARO_ENABLED=true
MANUAL_SEARCH_ENABLED=true

# HTTP behaviour
HTTP_TIMEOUT_SECONDS=20
HTTP_RETRIES=3
HTTP_RATE_LIMIT_PER_SECOND=3
```

### Laravel console (`console/.env`)

```env
DB_CONNECTION=pgsql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_DATABASE=bike_parts_watcher
DB_USERNAME=...
DB_PASSWORD=...
DB_SCHEMA=console

# Watcher schema connection (used by the parts-watch subprocess)
WATCHER_DB_SCHEMA=watcher
# WATCHER_DB_HOST / PORT / DATABASE / USERNAME / PASSWORD
# each falls back to the corresponding DB_* value if unset

QUEUE_CONNECTION=database
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme123
```

## Adapters

| Adapter | Status | Notes |
|---|---|---|
| eBay | **Live** | Free developer credentials from developer.ebay.com; multi-marketplace |
| Yahoo Auctions JP | **Live** | Best for vintage JDM parts; JP IP recommended |
| Buyee | **Live** | Yahoo Auctions proxy; works from any IP |
| Webike TW | **Live** | Bike-keyed catalog pages; requires `sync-catalog` |
| Monotaro | **Live (no prices)** | Industrial parts; prices load via JS and are not scraped |
| Manual search | **Live** | Local fallback; no external dependency |
| Webike JP | Stub | Geo-redirects to webike.tw from non-JP IPs |
| Croooober | Stub | Public domain defunct |
| Mercari JP | Stub | Pure SPA; needs Playwright |
| Rakuten | Stub | Blocked by Akamai; needs official API key (`RAKUTEN_APP_ID`) |
| Goobike | Stub | Pure SPA; needs Playwright |

See [`ADAPTERS.md`](ADAPTERS.md) for HTML structure, quirks, and the concrete steps to implement each stub.

## CLI reference

```bash
# Catalog
parts-watch sync-catalog                   # refresh bike_catalog from webike.tw

# Crawling (producer — enqueues jobs into watcher.crawl_jobs)
parts-watch crawl --bike <catalog_key>     # enqueue one bike, wait until done
parts-watch crawl-all                      # full sweep, returns immediately
parts-watch crawl-watches                  # re-crawl high-priority watch rows only
parts-watch search --query "exhaust" --bike-key suzuki-katana-1100-1990

# Worker (consumer — claims and executes jobs)
parts-watch worker --worker-id local-1 --adapters ebay,buyee,webike,manual_search

# Queue admin
parts-watch jobs                           # counts by status × adapter
parts-watch jobs --stuck                   # rows locked by a dead worker
parts-watch jobs --release-stale           # return stale-locked rows to pending
parts-watch jobs --prune --older-than-days 7
```

## Distributed workers

To route geo-restricted adapters through a JP host:

```bash
# JP host — connect to central Postgres over WireGuard/Tailscale
parts-watch worker --worker-id jp-1 \
  --adapters webike_jp,yahoo_auctions,mercari,monotaro,rakuten,goobike

# Central host
parts-watch worker --worker-id central-1 \
  --adapters ebay,buyee,webike,manual_search
```

> Do not expose Postgres directly to the public internet. Use WireGuard or Tailscale for the private link.

## Deployment

For production setup (Ubuntu 24.04, Nginx + PHP-FPM, systemd, WireGuard for the JP worker) see **[DEPLOYMENT.md](DEPLOYMENT.md)**, which includes a step-by-step installation checklist.

## Documentation

| File | Contents |
|---|---|
| [`CRAWLER_ARCHITECTURE.md`](CRAWLER_ARCHITECTURE.md) | End-to-end runtime: producer/worker/queue/ingest, data model, operational runbook |
| [`ADAPTERS.md`](ADAPTERS.md) | Per-source HTTP/parse details, status, and implementation path for each stub |
| [`MOTORCYCLE_PARTS_WATCHER_DATABASE.md`](MOTORCYCLE_PARTS_WATCHER_DATABASE.md) | ER diagram and sample queries |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Production deployment: Nginx, PHP-FPM, systemd units, JP worker setup |
| [`CLAUDE.md`](CLAUDE.md) | Project conventions for AI-assisted development |

## License

MIT
