# Crawler architecture reference

End-to-end reference for the motorcycle-parts crawler subsystem. Companion to `CLAUDE.md` (project conventions), `ADAPTERS.md` (per-source HTTP/parse details), and `MOTORCYCLE_PARTS_WATCHER_DATABASE.md` (ER diagram).

This document covers **how the crawler runs**, not how the web UI is structured. For Laravel-specific concerns (auth, routes, views, i18n) see `CLAUDE.md`.

---

## 1. Big picture

```
                          ┌──────────────────────────────────────────────────┐
   ┌──────────────┐       │         Postgres  bike_parts_watcher             │      ┌──────────────────────┐
   │  Laravel     │       │   ┌─────────────────┐    ┌─────────────────┐     │      │  Worker host(s)       │
   │  console     │──────►│   │ console schema  │    │ watcher schema  │     │◄─────│  parts-watch worker   │
   │  (Velzon UI) │       │   │ users           │    │ bike_catalog    │     │      │  --adapters X,Y,Z     │
   │              │       │   │ user_bikes      │    │ categories      │     │      │                       │
   │  Process::   │       │   │ parts_watches   │    │ sources         │     │      │  Outbound HTTP fetches │
   │  ::run() ──┐ │       │   │ sync_runs       │    │ listings        │     │      │  go to source sites    │
   └────────────┘ │       │   └─────────────────┘    │ listing_snapshots│    │      │  only.                 │
                  ▼       │                          │ crawl_jobs ◄────┼─────┼──────│                       │
   ┌──────────────────┐   │                          └─────────────────┘     │      └──────────────────────┘
   │ parts-watch CLI  │   └──────────────────────────────────────────────────┘
   │ (Typer)          │                              ▲
   │                  │  enqueue (producer side)     │
   │  sync-catalog    │──────────────────────────────┘
   │  crawl --bike X  │
   │  crawl-all       │
   │  crawl-watches   │
   │  search --query  │
   │  worker          │
   │  jobs            │
   └──────────────────┘
```

The system is split into **two sub-projects sharing one Postgres database**:

- `motorcycle_parts_watcher/` — Python 3.12+ async crawler. Owns the `watcher.*` schema. Exposes a Typer CLI named `parts-watch`.
- `console/` — Laravel 12 + PHP 8.2 web UI. Owns `console.*`, reads `watcher.*` over a second connection (`pgsql_watcher`), and shells out to `parts-watch` via queued jobs.

The two halves are coupled at the application layer (no DB-level FKs across schemas) so they can be migrated and deployed independently.

---

## 2. Lifecycle of one crawl request

### 2a. User-driven flow (e.g. "add a new bike to My Bikes")

```
[1] User submits POST /my-bikes
[2] MyBikesController::store
      ├─ resolve BikeCatalog row from (make, model_slug, year)
      ├─ firstOrCreate console.user_bikes
      └─ if newly created: SyncRun::create(kind=crawl_bike) + CrawlBikeJob::dispatch onQueue('sync')
[3] Laravel queue worker picks up CrawlBikeJob
      └─ Process::run(['parts-watch', 'crawl', '--bike', <key>], env={DATABASE_URL, DB_SCHEMA=watcher})
[4] parts-watch crawl --bike <key>
      ├─ CrawlProducer.enqueue_for_bike(key, enqueued_by="crawl:<key>:<uuid8>")
      │     - one watcher.crawl_jobs row per (eligible adapter, bike, query=NULL)
      │     - dedup via partial UNIQUE while status IN ('pending','running')
      └─ _wait_for(tag) polls jobs_for_enqueued_by until all are terminal
[5] Out-of-band, on each worker host:
      parts-watch worker --worker-id X --adapters …
      ├─ job_queue.claim_next  (UPDATE … FOR UPDATE SKIP LOCKED LIMIT 1)
      ├─ adapters/<name>.py → fetch(bike, query) → list[NormalizedListing]
      ├─ IngestService.ingest_listing  (categorize → hash → upsert → snapshot)
      └─ job_queue.complete  (status='completed', sets result_found / result_ingested)
[6] Wait-loop in step [4] returns; Laravel job exits 0 → SyncRun marked success
```

### 2b. Live search flow (`/parts/live-search`)

Same as above but `LiveSearchJob` builds `parts-watch search --query <q> [--bike-key …]`, priority is `PRIORITY_LIVE_SEARCH = 25` so it jumps queue ahead of background sweeps, and the watch-list row is `firstOrCreate`d at the Laravel side before dispatch (so revoked watches re-promote).

### 2c. Scheduled sweeps

`CrawlAllJob` and `CrawlWatchesJob` are dispatched **hourly** from Laravel's scheduler (`Console\Kernel::schedule`). Both check for an in-flight `SyncRun` of the same kind first so a slow sweep doesn't pile up duplicates. Without a running queue worker (`php artisan queue:work --queue=sync`) and a cron entry hitting `php artisan schedule:run` every minute, neither fires.

---

## 3. CLI surface (`parts-watch`, source: `motorcycle_parts_watcher/cli.py`)

| Command | Side | Purpose |
|---|---|---|
| `init-db` | one-shot | Run Alembic migrations, seed `sources` table |
| `sync-catalog` | one-shot | Refresh `bike_catalog` + `categories` from webike.tw |
| `crawl --bike <key> [--no-wait] [--timeout 1500]` | producer | Enqueue jobs for one bike; block until terminal by default |
| `crawl-all [--skip-watches]` | producer | Enqueue bike sweep + watch sweep, return immediately |
| `crawl-watches` | producer | Enqueue only high-priority `parts_watches` rows |
| `search --query <q> [--bike-key …] [--no-wait]` | producer | Ad-hoc keyword search across active bikes |
| `worker --worker-id X --adapters a,b,c [--once] [--poll-seconds 5]` | worker | Long-lived consumer; claims jobs filtered by adapter allowlist |
| `jobs [--stuck] [--release-stale] [--prune --older-than-days 7]` | admin | Queue inspection / maintenance |
| `report --format markdown\|html` | admin | Reporting helpers |
| `export --format csv\|json` | admin | Bulk export of `listings` |

**Wait semantics** — for `crawl --bike` and `search`, the CLI tags each enqueued row with `enqueued_by="<kind>:<key>:<uuid8>"` and polls `jobs_for_enqueued_by(tag)` until every row reaches `completed` or `failed`. This is what lets Laravel's `SyncRun` machinery treat the whole fan-out as a single unit of work even though the queue handles the actual scrape.

---

## 4. Data model

### 4a. `watcher.crawl_jobs` (the queue, migration `0005_crawl_jobs.py`)

Columns: `id BIGSERIAL PK, bike_catalog_key, adapter, query TEXT, original_query TEXT, priority INT DEFAULT 100, status VARCHAR(20) DEFAULT 'pending', attempts INT, max_attempts INT DEFAULT 3, locked_by, locked_at, started_at, completed_at, last_error TEXT, result_found INT, result_ingested INT, watch_ids INT[], enqueued_by, created_at`.

Indexes:

- `ix_crawl_jobs_claim` — `(status, adapter, priority, id)` — drives the claim query.
- `ix_crawl_jobs_active_status` — `(status) WHERE status IN ('pending','running')` — health / visibility.
- `ix_crawl_jobs_enqueued_by` — `(enqueued_by)` — drives the wait-loop.
- `uq_crawl_jobs_inflight` — **partial UNIQUE** on `(adapter, bike_catalog_key, COALESCE(query, ''))` while `status IN ('pending','running')`. This is what makes `enqueue` idempotent.

Status transitions: `pending → running → completed | failed`. On exception with attempts left, the worker resets to `pending` and clears the lock, so retries do not consume queue rows.

Priority lower = sooner. Constants in `services/crawl.py`:

```python
PRIORITY_LIVE_SEARCH = 25   # user is staring at the UI
PRIORITY_WATCH_SWEEP = 50
PRIORITY_BIKE_SWEEP  = 100
```

### 4b. `watcher.listings` (migration `0001_initial_schema.py`)

The output of all crawls. Key columns:

- `(source_name, source_item_id)` UNIQUE — primary dedup key.
- `url` UNIQUE — secondary dedup.
- `bike_key` indexed — lookup by bike.
- `content_hash` (SHA256, hex) indexed — change-detection key (4th-tier dedup, see §6).
- `category, subcategory, part_number, fitment_text` — populated by `utils/categorizer.classify()` and adapter parsing.
- `first_seen_at, last_seen_at` — tracked per crawl so Parts UI can show "last seen 3 hours ago".
- `raw_json` — full source payload preserved for forensics.
- `pg_trgm` GIN indexes (migration `0004_search_indexes.py`) on `title`, `description`, `part_number` for fast ILIKE.

`watcher.listing_snapshots` — one row per crawl per listing (`listing_id, checked_at, price_amount, availability_status, raw_json`). Drives the price-history table on the listing detail page.

### 4c. `watcher.bike_catalog` (migration `0002_bike_catalog.py`)

Source of truth for what bikes exist. Populated entirely by `services/catalog_sync.py` (see §8). `catalog_key` is the UNIQUE string identity used everywhere downstream:

```
suzuki-katana-1100-1990              # year_start == year_end
suzuki-gsx1300r-2003-2007            # year-range variant
yamaha-mt-09                         # umbrella row, year_start == year_end == 0
```

`year_start == year_end == 0` means "year unknown" — common for umbrella rows when the `/md/{id}` detail page has no year-range variants. `BikeRef.display_year` returns empty in that case so adapters that template `"{make} {model} {year}"` must strip trailing whitespace.

### 4d. `watcher.categories` (migration `0003_categories.py`)

Self-referencing tree (`parent_id → categories.id`). Populated by `_upsert_taxonomy()` in catalog sync. Static — TOP_CATEGORIES + SUBCATEGORIES are hardcoded constants mirroring the webike.tw nav tree.

---

## 5. Producer and worker (`services/crawl.py`)

### 5a. `CrawlProducer`

Three public methods, all returning `EnqueueSummary{ by_adapter: dict[str,int], skipped: dict[str,int] }`:

- `enqueue_for_bike(catalog_key, query=None, priority=None, enqueued_by=None, watch_ids=None)`
- `enqueue_all(query=None, include_watches=True, enqueued_by=None)` — joins `console.user_bikes` cross-schema for active bikes.
- `enqueue_watches(enqueued_by=None)` — `WHERE is_high_priority=TRUE`.

For each `(bike, adapter)`, the producer translates the query via `translate_for_adapter()` so the worker gets a per-adapter localized string. The producer is **the only side** that imports the translation dictionary; this keeps workers small and lets future workers run on hosts without the `utils/i18n.py` data file.

Skipped reasons land in `summary.skipped` so the CLI can surface them: adapter disabled, dedup hit on inflight UNIQUE, etc.

### 5b. `CrawlWorker`

```python
worker = CrawlWorker(session_factory, settings, worker_id="local-1",
                     adapters=["ebay","webike","manual_search"])
worker.run_forever(poll_seconds=5)
```

`run_once()` loop:

1. `job_queue.claim_next(worker_id, adapters)` — atomic UPDATE … FOR UPDATE SKIP LOCKED.
2. Fetch `BikeRef` via `bikes.load_bike_by_key`.
3. `await adapter.fetch(bike, query)` → `list[NormalizedListing]`.
4. For each listing, `IngestService.ingest_listing(l)` (see §6).
5. If job has `watch_ids`, increment `console.parts_watches.match_count` by **the count from this single job**, and set `last_crawled_at = now()`. (Lifetime additive, not per-sweep.)
6. `job_queue.complete(id, found, ingested)` — clears lock, sets `completed_at`.
7. On exception: `job_queue.fail(id, error)` — re-queues if `attempts < max_attempts`, else marks `failed`.

Every ~60 iterations the worker calls `release_stale(stale_after_minutes=30)` so a crashed peer's locked rows return to `pending`.

### 5c. Queue helpers (`services/job_queue.py`)

The claim is the only non-obvious SQL:

```sql
UPDATE watcher.crawl_jobs
   SET status='running', locked_by=:worker_id, locked_at=now(),
       started_at=COALESCE(started_at,now()), attempts=attempts+1
 WHERE id = (
     SELECT id FROM watcher.crawl_jobs
      WHERE status='pending' AND adapter = ANY(:adapters)
      ORDER BY priority, id
        FOR UPDATE SKIP LOCKED
      LIMIT 1
 )
RETURNING …
```

`SKIP LOCKED` is the whole point — multiple workers running concurrently never block each other; they just skip rows another worker is currently dequeuing.

`enqueue` uses `INSERT … ON CONFLICT DO NOTHING` against the partial UNIQUE described in §4a, returning `id` or `None` for skipped duplicates.

---

## 6. Ingest pipeline (`services/ingest.py`)

`IngestService.ingest_listing(NormalizedListing) -> Listing` runs:

1. `classify(title, description)` → `(category, subcategory)` from `utils/categorizer.py`. First substring rule wins; falls back to `("unknown", None)`.
2. `compute_content_hash(listing)` — SHA256 over a normalized JSON payload (lowercased title/description, stringified price, etc.) defined in `utils/hashing.py`. Used as 4th-tier dedup and for cheap change detection on snapshot writes.
3. `_find_existing()` — four-tier dedup:
   1. `(source_name, source_item_id)` UNIQUE.
   2. URL exact match.
   3. Title similarity ≥ 0.92 among same-bike candidates of the same source (and `manual_search`).
   4. `content_hash` match.
4. If found: update mutable columns (price, condition, shipping, seller info, `last_seen_at`).
   If new: INSERT and flush.
5. **Always** append a `ListingSnapshot` row (`checked_at = now()`, current price, current `availability_status`, full `raw_json`) — even if nothing changed. This guarantees the price-history table reflects every successful crawl.

The 4-tier dedup is what lets multiple sources (eBay US vs. eBay GB vs. Buyee) all surface the same physical listing without duplicating rows in `listings`.

---

## 7. Adapters

All adapters implement the `ListingAdapter` Protocol (`adapters/base.py`):

```python
class ListingAdapter(Protocol):
    name: str
    enabled: bool
    preferred_query_lang: str | None  # used by translate_for_adapter
    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]: ...
```

Two contracts they must hold:

1. **Pure** — fetch and normalize only. No DB writes. `IngestService` is the only writer.
2. **Use `utils/http.build_async_client` + `AsyncRateLimiter` + `with_retries`** — never raw `httpx`. This is what enforces the global rate limit and retry policy.

Per-adapter quick reference:

| Name | `source_name` | Method | Auth | State | Lang | Notes |
|---|---|---|---|---|---|---|
| eBay (`ebay.py`) | `ebay` | OAuth2 + Browse API JSON | Client credentials | live | en | Fans out across `EBAY_MARKETPLACE_IDS` (default `EBAY_US`); cross-marketplace dedup via `seen` set |
| Buyee (`buyee.py`) | `buyee` | HTML scrape `buyee.jp/item/search/query/{q}?lang=en` | none | live | ja | Yahoo Auctions JP via the buyee.jp proxy; reachable from non-JP IPs; prefers Current > Buyout > Price labels |
| Webike (`webike.py`) | `webike` | HTML scrape `webike.tw/md/{ID}` | none | live | zh-TW | schema.org microdata `meta[itemprop=price]`; image walk goes up to sibling `.item__header__img` |
| Webike JP (`webike_jp.py`) | `webike_jp` | stub | — | **blocked** | — | `japan.webike.net` redirects non-JP IPs to webike.tw; needs JP egress |
| Yahoo Auctions (`yahoo_auctions.py`) | `yahoo_auctions` | HTML scrape `auctions.yahoo.co.jp/search/search` | none | JP-only | ja | Web API was shut down 2018; HTML scrape is the only path; tracks 即決 (buy-now) flag |
| Manual search (`manual_search.py`) | `manual_search` | local file or seed URLs | none | live | — | Reads `manual_listings.json` if present, else emits Google-search seeds with `source_item_id={bike_key}-seed-<sha1[:8]>-<idx>` so query variants get distinct rows |
| Croooober (`croooober.py`) | `croooober` | stub | — | **blocked** | — | Domain dead — redirects to upgarage.com which 404s |
| Mercari (`mercari.py`) | `mercari` | stub | — | **blocked** | — | SPA + DPoP-signed JWT API; needs Playwright |
| Monotaro (`monotaro.py`) | `monotaro` | HTML scrape `monotaro.com/s/?q={q}` | none | live | ja | No price in static HTML (Next.js RSC); price arrives later via snapshot pass |
| Rakuten (`rakuten.py`) | `rakuten` | stub | — | **blocked** | — | Akamai bot wall; must migrate to official `webservice.rakuten.co.jp` API with `RAKUTEN_APP_ID` |
| Goobike (`goobike.py`) | `goobike` | stub | — | **blocked** | — | SPA gated by anti-bot cookie |

Adapters are toggled in `.env` via `<NAME>_ENABLED=true`. The producer skips disabled ones at enqueue time, so a worker running with `--adapters croooober` simply gets nothing.

For per-adapter HTML structure / quirks, `ADAPTERS.md` is the deeper reference.

---

## 8. Catalog sync (`services/catalog_sync.py`) — separate flow

Catalog sync is **not** part of the listing pipeline. It populates `bike_catalog` (the dropdowns in My Bikes) and `categories` (the taxonomy). It runs synchronously from one host, no queue, no adapters, no workers.

`async sync_catalog(session, settings) -> SyncStats` runs three passes:

1. **Categories (synchronous, instant)** — `_upsert_taxonomy()` upserts the static `TOP_CATEGORIES` + `SUBCATEGORIES` constants from `catalog_sync.py`.
2. **Maker discovery** — fetch `https://www.webike.tw/`, regex-extract every `/mf/{MAKE}/` slug from the page chrome (handles `HARLEY-DAVIDSON`, `TW_SUZUKI`, etc.). Falls back to `DEFAULT_MAKES = ("HONDA","YAMAHA","SUZUKI","KAWASAKI")` if the fetch fails.
3. **Bikes per maker × CC bucket** — for each `(make, cc_slug)` in `CC_BUCKETS = (("50",50), ("125",125), ("250",250), ("400",400), ("750",750), ("1000",1000), ("1001",None))`:
   - Fetch `/mf/{MAKE}/{slug}`, parse the bike index → emit umbrella `_BikeRow` per model (year_start = year_end = 0).
   - Upsert each umbrella, then for each fan out `_sync_md_variants()`:
     - Fetch `/md/{id}`, regex-parse `年式 : YYYY ~ YYYY` anchors (`_VARIANT_LINK_RE`).
     - Open-ended end-years (`年式 : 2021 ~  ` for current models) get `current_year` filled in.
     - Upsert one `bike_catalog` row per variant with the deep `/md/{id}/kt/{kt}` URL.

`catalog_key` shape:

| year_start, year_end | catalog_key |
|---|---|
| 0, 0 | `{make_lower}-{model_slug}` |
| Y, Y | `{make_lower}-{model_slug}-Y` |
| A, B | `{make_lower}-{model_slug}-A-B` |

`BikeCatalog::yearsForModel` (Laravel side) only emits the `0` entry if **no** real year-range variants exist for that model — so the dropdown shows actual years when we have them.

The sync commits per `(make, cc_bucket)`, so a partial failure leaves earlier makes persisted. A failure mid-HONDA today doesn't blank yesterday's HONDA rows.

---

## 9. Laravel ↔ Python bridge (`console/app/Jobs/`)

All Laravel jobs that drive the crawler extend `RunPartsWatchJob.php`. The base class:

- `$timeout = 1800` (30 min), `$tries = 1`.
- On `handle()`, validates the `parts-watch` binary, marks the `SyncRun` as `running`, then:
  ```php
  $env = [
      'DATABASE_URL' => …WATCHER_DB_*…,
      'DB_SCHEMA' => env('WATCHER_DB_SCHEMA','watcher'),
  ];
  $result = Process::path($cwd)->env($env)->timeout($this->timeout)->run($argv);
  $output = $result->output() . "\n" . $result->errorOutput();
  if ($result->successful()) $run->markSuccess($output);
  else                       $run->markFailed("Exit {$result->exitCode()}\n".$output);
  ```
- `failed(\Throwable $e)` falls back to `markFailed("Job exception: ".$e->getMessage())`.

The env override is **load-bearing**. Without it, the Python child inherits Laravel's `DB_SCHEMA=console` from the parent shell and queries `console.sources` (which doesn't exist).

Subclass argv:

| Job | argv |
|---|---|
| `SyncWebikeCatalogJob` | `['sync-catalog']` |
| `CrawlAllJob` | `['crawl-all']` |
| `CrawlWatchesJob` | `['crawl-watches']` |
| `CrawlBikeJob` | `['crawl', '--bike', $catalogKey]` |
| `LiveSearchJob` | `['search', '--query', $query, '--bike-key', …]` |

All five dispatch on the `sync` queue. They require `php artisan queue:work --queue=sync` to be running, and the hourly two (`CrawlAllJob`, `CrawlWatchesJob`) additionally require a cron entry hitting `php artisan schedule:run` every minute.

**`SyncRun` truncation gotcha** — `SyncRun::markFailed` keeps only the **last 4000 chars** of the captured output. If Python crashes with a SQLAlchemy bulk-insert error, the bind-param dump can blow past 4000 chars on its own and the actual exception class at the head of the traceback is lost. To recover full tracebacks, run `parts-watch <cmd>` directly in a shell.

---

## 10. Translation (`utils/i18n.py`)

Three locales: `en`, `ja`, `zh-TW`. Translation runs at **producer time**, not at the worker — so workers can run on hosts that don't ship the dictionary.

```python
translate(text, target_lang)         -> str   # phrase-greedy lookup, unknown tokens pass through
translate_for_adapter(query, adapter) -> str  # uses adapter.preferred_query_lang
detect_lang(text) -> "ja" | "zh-TW" | "en"   # Hiragana/Katakana → ja; Han-only → zh-TW; else en
```

Each adapter declares `preferred_query_lang` (`"en"`, `"ja"`, `"zh-TW"`, or `None`). The producer calls `translate_for_adapter(user_query, adapter)` once per adapter and writes the result into `crawl_jobs.query` while preserving the user's literal in `original_query`.

Manual search keeps `preferred_query_lang=None` deliberately — the watch-list UI shows what the user typed, not a translated form.

---

## 11. Distributed worker deployment

For geo-routing (e.g. JP-locale scrapers from a JP host to avoid IP blocks):

```
# JP host (residential / VPS in Japan)
parts-watch worker --worker-id jp-1 \
   --adapters webike_jp,yahoo_auctions,croooober,mercari,monotaro,rakuten,goobike

# Central host (anywhere)
parts-watch worker --worker-id central-1 \
   --adapters ebay,buyee,webike,manual_search
```

Both connect to the same central Postgres over a private link (WireGuard / Tailscale — never expose Postgres to the public internet). A worker only fetches a `BikeRef` once per claim (single SELECT), then the heavy outbound HTTP is the adapter scrape from the worker's own egress IP.

`parts-watch jobs` gives a quick cluster-health view; `parts-watch jobs --stuck` surfaces rows whose worker died mid-run.

---

## 12. Operational runbook

### Daily / on-demand

```bash
# Status snapshot
parts-watch jobs                                         # counts by (status × adapter)
psql -d bike_parts_watcher -c "SELECT make, COUNT(*) FROM watcher.bike_catalog GROUP BY make;"
psql -d bike_parts_watcher -c "SELECT status, COUNT(*) FROM watcher.crawl_jobs GROUP BY status;"

# Recover dead workers
parts-watch jobs --release-stale                          # return stale-locked → pending
parts-watch jobs --prune --older-than-days 7              # clean old completed/failed
```

### Recovering from a failed sync_run

```bash
# Look at recent Laravel-driven runs
psql -d bike_parts_watcher -c \
  "SELECT id, kind, status, created_at, finished_at FROM console.sync_runs ORDER BY id DESC LIMIT 10;"

# The output_excerpt is truncated to 4000 chars. For a real traceback,
# rerun the same parts-watch command directly in a shell:
source .venv/bin/activate
parts-watch sync-catalog 2>&1 | tee /tmp/catalog-sync.log
```

### Adding a new adapter (concrete steps)

1. Create `adapters/<name>.py` implementing `ListingAdapter` (`name`, `enabled`, `preferred_query_lang`, `async fetch`).
2. Use `build_async_client(settings)` + `AsyncRateLimiter(settings.http_rate_limit_per_second)` + `with_retries`. No raw `httpx`.
3. Add `<NAME>_ENABLED` (and any auth env) to `motorcycle_parts_watcher/config.py:Settings`.
4. Wire it into `_build_adapters()` in `services/crawl.py`.
5. Add a `sources` row (or rely on `init-db` seeding).
6. Document in `ADAPTERS.md` (HTML structure / API shape, quirks).
7. Add tests under `tests/`.

The producer will start enqueueing for it on the next sweep; you need a worker running with `--adapters <name>` (or `--adapters` containing it) to actually consume.

### Required env (top-level `.env` for the Python crawler)

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher
EBAY_ENABLED=true   EBAY_CLIENT_ID=…   EBAY_CLIENT_SECRET=…   EBAY_MARKETPLACE_ID=EBAY_US
EBAY_MARKETPLACE_IDS=EBAY_US,EBAY_GB,EBAY_DE,EBAY_AU,EBAY_IT
WEBIKE_ENABLED=true
BUYEE_ENABLED=true
MANUAL_SEARCH_ENABLED=true
HTTP_TIMEOUT_SECONDS=20   HTTP_RETRIES=3   HTTP_RATE_LIMIT_PER_SECOND=3
```

`console/.env` additionally needs `WATCHER_DB_*` (the override values used by `RunPartsWatchJob`), `QUEUE_CONNECTION=database`, `ADMIN_EMAIL`/`ADMIN_PASSWORD`, and the standard Laravel app keys.

---

## 13. Known gotchas

- **The catalog sync's `output_excerpt` truncates to the last 4000 chars.** A SQLAlchemy bulk-insert traceback's bind-param dump can fill that buffer on its own, hiding the exception class at the top. For real diagnosis, rerun in a shell with `2>&1 | tee`.
- **`year_start == year_end == 0` means "year unknown".** `BikeRef.display_year` returns `""` in that case; adapters must `.strip()` their templated titles.
- **`console.parts_watches.match_count` is additive across per-adapter completions, not per-sweep.** Every watch-job completion does `match_count = match_count + :ingested_in_this_job`. New semantic is "lifetime ingested for this watch."
- **A worker handling an adapter gets nothing if no producer is enqueueing for it.** Adapters whose `Source` row is `enabled=false` are skipped at enqueue time — disable a source there to drain it out cleanly.
- **Geo-redirects are silent.** `webike_jp` / `goobike` / etc. return 200 OK from non-JP IPs but the body is the redirected page. If a JP-locale adapter is suspiciously empty, check the response URL, not the status code.
- **Rate limiter is per-process, not global.** Two workers on the same host both running with `HTTP_RATE_LIMIT_PER_SECOND=3` will hit the upstream at 6/sec. Geographic worker split helps because each host has its own rate budget.
- **Don't expose Postgres publicly.** Use WireGuard/Tailscale for distributed workers.

---

## 14. Where to look next

| You want to … | Read |
|---|---|
| Understand the per-adapter HTML/API shape | `ADAPTERS.md` |
| Understand the DB schema | `MOTORCYCLE_PARTS_WATCHER_DATABASE.md` + `alembic/versions/000{1..5}_*.py` |
| Understand the Laravel side (auth, routes, i18n, views) | `CLAUDE.md` |
| Add a new adapter | `motorcycle_parts_watcher/adapters/base.py` + any existing adapter as a template |
| Trace a crawl end-to-end | `cli.py:crawl` → `services/crawl.py:CrawlProducer` → `services/job_queue.py:enqueue` → `services/crawl.py:CrawlWorker` → `adapters/<name>.py:fetch` → `services/ingest.py:ingest_listing` |
| Fix a stuck queue | §12 "Recover dead workers" |
