# Adapters Guide

This document explains every source adapter in `motorcycle_parts_watcher/adapters/`: what each one does, what it can and cannot pull, and exactly what you need to set to turn it on.

---

## 1. The contract

Every adapter implements the same protocol from `adapters/base.py`:

```python
class ListingAdapter(Protocol):
    name: str         # used as source_name on every row it produces
    enabled: bool     # gate #1 (driven by env)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]: ...
```

**An adapter only fetches and normalizes.** It never writes to the database. Every `NormalizedListing` it returns is handed to `services/ingest.py`, which categorizes, hashes, dedupes (`UNIQUE(source_name, source_item_id)` and `UNIQUE(url)`), upserts into `watcher.listings`, and always appends a row to `watcher.listing_snapshots` for price-history tracking.

**Two enable gates have to be open** for an adapter to actually run during a crawl. This is intentional — the env gate is the developer/ops switch; the DB gate lets you flip a source on/off per-environment without redeploying:

1. `<adapter>_ENABLED=true` in `.env` (drives the adapter's `self.enabled` field)
2. `watcher.sources.enabled = true` for that source's `name`

`services/crawl.py::_crawl_one` filters by both. If a source seems silent, check both.

The `query` parameter on `fetch()` is what powers the `/parts/live-search` button in the console — when provided, the adapter appends or substitutes it into its search terms. When `None`, the adapter falls back to the bike's `make + model + year`.

---

## 2. Adapter catalogue

Status legend:
- **Live** — real implementation, returns rows
- **Live (no prices)** — returns titles + images + URLs but the source's static HTML doesn't expose prices
- **Stub** — file exists, logs a clear "not implemented" message, returns `[]`. Use these as documentation of what would be needed to turn the source on.

| Adapter | `name` | Status | Source type | Notes |
|---|---|---|---|---|
| eBay | `ebay` | **Live** (needs creds) | OAuth REST API | Multi-marketplace fan-out |
| Yahoo Auctions JP | `yahoo_auctions` | **Live** | HTML scrape | Best for vintage JDM bikes |
| Buyee | `buyee` | **Live** | HTML scrape | JP proxy; same Yahoo Auctions inventory but reachable from non-JP IPs and renders English |
| Webike TW | `webike` | **Live** | HTML scrape | Bike-keyed (`/md/{ID}` pages) |
| Monotaro | `monotaro` | **Live (no prices)** | HTML scrape | Industrial parts catalog |
| Manual search | `manual_search` | **Live** | Local fallback | Query-driven only |
| Webike JP | `webike_jp` | Stub | — | Geo-redirected to webike.tw |
| Croooober | `croooober` | Stub | — | Public catalog domain dead |
| Mercari JP | `mercari` | Stub | — | Pure SPA |
| Rakuten | `rakuten` | Stub | — | Akamai-blocked; needs API key |
| Goobike Parts | `goobike` | Stub | — | Pure SPA |

---

## 3. Live adapters — details

### eBay (`ebay`)

**What it pulls.** All listings (new, used, parts, whole bikes) matching `<make> <model> <year> parts` (or `<make> <model> <year> <query>` for live search) across one or more eBay marketplaces.

**How it works.** OAuth client-credentials grant against `api.ebay.com/identity/v1/oauth2/token`, then `GET /buy/browse/v1/item_summary/search` per marketplace. The token is fetched once per `fetch()` call and reused across all marketplaces. Marketplace calls run concurrently via `asyncio.gather`; results are deduped on `itemId` within the batch (eBay item IDs are globally unique, so a listing cross-listed in `EBAY_US` and `EBAY_GB` only appears once).

**Configuration.**

```env
EBAY_ENABLED=true
EBAY_CLIENT_ID=<from developer.ebay.com>
EBAY_CLIENT_SECRET=<from developer.ebay.com>

# Comma-separated; overrides the singular EBAY_MARKETPLACE_ID when set.
EBAY_MARKETPLACE_IDS=EBAY_US,EBAY_GB,EBAY_DE,EBAY_AU,EBAY_IT

# Legacy single-marketplace fallback (still respected if EBAY_MARKETPLACE_IDS is empty).
EBAY_MARKETPLACE_ID=EBAY_US
```

Supported marketplace IDs include `EBAY_US`, `EBAY_GB`, `EBAY_DE`, `EBAY_AU`, `EBAY_IT`, `EBAY_FR`, `EBAY_ES`, `EBAY_CA`, `EBAY_JP`, `EBAY_NL`, `EBAY_BE`. eBay's full list is at developer.ebay.com → "Marketplace IDs."

**Getting credentials.** Register a free developer account at developer.ebay.com, create an application, copy the production "App ID" and "Cert ID" into `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`. Free tier is generous (5000 calls/day per app); the Browse API requires no user consent.

**Per-row metadata.** `raw_json._marketplace_id` carries the originating marketplace. The UI can group by country with this.

**Without credentials.** The adapter early-returns `[]` and does not crash the crawl.

---

### Yahoo Auctions Japan (`yahoo_auctions`)

**What it pulls.** Active auction listings on `auctions.yahoo.co.jp` matching `<make> <model> [<query>]` (or `<make> <model> <year>` when no query is given). Strong yield for vintage JDM bikes (Katana 1100 typically returns 50 hits; Hayabusa 30+).

**How it works.** Plain HTML scrape of `https://auctions.yahoo.co.jp/search/search?p=<q>&va=<q>&n=50`. Each result is an `<li class="Product">` containing:

- `a[href*="/jp/auction/"]` — auction URL; ID is the last URL segment (sometimes letter-prefixed: `1225854667`, `v1228694564`, `l1228671446`)
- `<h3>` — title
- `.Product__priceValue.u-textRed` — current bid price (JPY)
- second `.Product__price` — buy-now price (when present)
- `.Product__bidWrap` — bid count
- `<img>` inside `.Product__image`

**Configuration.**

```env
YAHOO_AUCTIONS_ENABLED=true
```

No API key. No rate-limit headaches at modest crawl rates (default is 3 req/s globally, shared by all adapters via `AsyncRateLimiter`).

**Per-row metadata.** `raw_json` carries `search_terms`, `bid_count`, `has_buy_now`.

---

### Buyee (`buyee`)

**What it pulls.** Active Yahoo Auctions JP listings as surfaced by Buyee, the JP proxy-buying service. Same inventory as `yahoo_auctions`, different DOM, renders English chrome and is reachable from non-JP IPs without geo issues. Use as a fallback or complement to `yahoo_auctions` (and a replacement when running from a region that gets challenged on `auctions.yahoo.co.jp`).

**How it works.** Plain HTML scrape of `https://buyee.jp/item/search/query/<q>?lang=en`. Each `<li class="itemCard">` carries:

- `a[href*="/item/jdirectitems/auction/{ID}"]` — anchor; ID is the original Yahoo Auctions ID (e.g. `v1228666690`)
- `.itemCard__itemName a` — title (Japanese, untranslated)
- `.g-priceDetails__item .g-price` — price text like `1,200 YEN`. The accompanying `.g-title` distinguishes `Current Price` (auction bid), `Buyout Price` (即決), and `Price` (store fixed-price). The adapter prefers Current → Buyout → Price.
- `img.g-thumbnail__image[data-src]` — lazy-loaded image
- `.itemCard__infoItem` (label "Number of Bids") — bid count
- `.auctionSearchResult__statusList` containing `STORE` — flags STORE-seller listings

Item IDs are the Yahoo Auctions IDs, but `source_name="buyee"` is used so rows don't collide with the `yahoo_auctions` adapter when both are enabled.

**Configuration.**

```env
BUYEE_ENABLED=true
```

No API key.

**Per-row metadata.** `raw_json` carries `search_terms`, `price_label` (`Current Price` / `Buyout Price` / `Price`), `bid_count`, `is_store`.

---

### Webike Taiwan (`webike`)

**What it pulls.** Aftermarket parts listed under a specific bike's catalog page on `webike.tw` (e.g. `/md/679` for the Katana). Returns 20-30 priced products per bike.

**How it works.** Each user-bike row in `console.user_bikes` joins to a `watcher.bike_catalog` row that carries a `webike_url` (populated by `services/catalog_sync.py`). The adapter fetches that URL — **not** a search page, since webike's keyword search is JS-rendered. On the model page, every priced product card uses schema.org microdata:

```html
<div class="item__body p-2">
  <a href="/sd/{ID}">…</a>
  <meta itemprop="price" content="499">
  <meta itemprop="priceCurrency" content="TWD">
</div>
```

The parser iterates `meta[itemprop="price"]` (skipping the unpriced "you may also like" anchors), walks up to the parent containing the `/sd/` anchor, then walks up *one more level* to find the product image (it lives in a sibling `.item__header__img` outside `item__body`). When a `query` is supplied (live search), results are filtered by case-insensitive substring match against the title — a true keyword search isn't possible without JS.

**Configuration.**

```env
WEBIKE_ENABLED=true
```

The catalog sync (`parts-watch sync-catalog`) is what populates `bike_catalog` rows with `webike_url`. Without that, the adapter has no entry point for a bike. The list of makers walked by the sync is discovered automatically from `https://www.webike.tw/` on each run (every `/mf/{MAKE}/` link in the page chrome) — there's no whitelist to maintain.

**Webike JP (`webike_jp`) is a separate stub** — see §4.

---

### Monotaro (`monotaro`)

**What it pulls.** Industrial / OEM parts matching the bike name or query: oil filters, brake pads, air filters, bolts, electrical relays. Mostly Japanese sellers, JPY pricing on the product detail pages (not on search).

**How it works.** HTML scrape of `https://www.monotaro.com/s/?q=<q>`. Static HTML contains the product anchors (`a[href*="/g/{8-digit-code}/"]`) along with images and titles in `<img alt>`, but **prices are loaded asynchronously via Next.js streaming RSC chunks** (`self.__next_f.push([...])`). Static parsing yields title + image + URL only; prices are `null`. To recover prices, a follow-up fetch of each product detail page would be needed (not implemented).

**Configuration.**

```env
MONOTARO_ENABLED=true
```

No API key.

**When it's useful.** Monotaro is at its best when the bike-derived search returns generic noise. Use the live-search bar in the console with specific part names (`オイルフィルター`, `ブレーキパッド`) to narrow it.

---

### Manual search (`manual_search`)

**What it pulls.** A query-driven fallback that surfaces the user's typed query as a tracked listing even when no upstream source returned anything. Useful for the watch-list flow — users get a row in the watch list immediately, and the row stays as a "seen" placeholder so the live-source fallback button has somewhere to attach.

**How it works.** Synthesizes a `NormalizedListing` from the bike + query. The `source_item_id` is a hash of the query so that different queries on the same bike produce distinct rows (one per query), instead of all colliding on the bike's ID.

**Configuration.**

```env
MANUAL_SEARCH_ENABLED=true
```

Always on by default; no external dependencies.

---

## 4. Stub adapters — what blocks them and how to enable

Each stub returns `[]` and logs a one-line `INFO` message explaining the blocker. Open the file to see the full notes (every stub has a docstring with the path forward).

| Stub | Blocker | Path forward |
|---|---|---|
| `webike_jp.py` | `japan.webike.net` and `www.webike.net` 200-redirect to `webike.tw` from non-Japan IPs | Route requests through a JP egress (residential proxy or VPN), then port the `WebikeAdapter` (`/md/{ID}` schema.org pattern) to the JP DOM. |
| `croooober.py` | `www.croooober.com` 301s to a defunct `ec.upgarage.com` (404 everywhere) | The Up-Garage corporate rebrand left no working public catalog. Watch for a successor URL or implement against an Up-Garage Mercari Shops account. |
| `mercari.py` | Pure React SPA. No SSR data, no JSON-LD. Product list comes from `api.mercari.jp/search_index/search` which requires a per-device DPoP-signed JWT. | Easiest: Playwright headless against `jp.mercari.com/search?keyword=…`, ~3-5s/query. Hardest but cheapest: implement Mercari's DPoP auth flow against `api.mercari.jp/v2/entities:search`. |
| `rakuten.py` | `search.rakuten.co.jp` returns a 43-byte Akamai bot-challenge page regardless of headers/cookies | Use the official Rakuten Web Service: register at webservice.rakuten.co.jp for a free Application ID, set `RAKUTEN_APP_ID` in `.env`, then call `GET https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601?applicationId=…&keyword=…&hits=30&format=json`. The response is directly mappable to `NormalizedListing`. |
| `goobike.py` | Pure SPA; `/parts/?word=…` returns a ~4kB shell with no inline product data | Playwright headless. Goobike updates daily, so a nightly cron is enough. |

Each stub still respects the same enable gates (`<NAME>_ENABLED` env + `watcher.sources.enabled`), so you can turn one on at any time without code changes once you've replaced the stub body.

---

## 5. Configuration reference

### Top-level `.env` (Python crawler)

```env
# Required
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/bike_parts_watcher
DB_SCHEMA=watcher

# eBay
EBAY_ENABLED=true
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_US
EBAY_MARKETPLACE_IDS=EBAY_US,EBAY_GB,EBAY_DE,EBAY_AU,EBAY_IT

# Other live sources
YAHOO_AUCTIONS_ENABLED=true
BUYEE_ENABLED=true
WEBIKE_ENABLED=true
MONOTARO_ENABLED=true
MANUAL_SEARCH_ENABLED=true

# Stubs (off by default; flipping on without implementing won't crash anything,
# the adapter just logs and returns [])
WEBIKE_JP_ENABLED=false
CROOOOBER_ENABLED=false
MERCARI_ENABLED=false
RAKUTEN_ENABLED=false
RAKUTEN_APP_ID=
GOOBIKE_ENABLED=false

# Shared HTTP behaviour (used by every adapter via utils/http.py)
HTTP_TIMEOUT_SECONDS=20
HTTP_RETRIES=3
HTTP_RETRY_BACKOFF_SECONDS=1
HTTP_RATE_LIMIT_PER_SECOND=3   # global rate limit shared across ALL adapters
```

### Database — `watcher.sources`

This table is the second enable gate. To toggle a source on/off without restarting anything:

```sql
UPDATE watcher.sources SET enabled = true  WHERE name = 'monotaro';
UPDATE watcher.sources SET enabled = false WHERE name = 'mercari';

-- Inspect current state
SELECT name, enabled FROM watcher.sources ORDER BY name;
```

Source rows are seeded by `parts-watch init-db` (legacy four) and were inserted by hand when the JP-source batch landed (`webike_jp`, `croooober`, `mercari`, `rakuten`, `monotaro`, `goobike`).

---

## 6. Operating notes

### How an adapter participates in a crawl

`services/crawl.py::CrawlService.adapters` is a fixed list of every registered adapter instance. On every `crawl-all`:

1. **Bike sweep** — for each `bike` in `console.user_bikes`, the active adapters are filtered down by `enabled and name in {row.name for row in watcher.sources where enabled=true}`, then each adapter's `fetch(bike, query=None)` is awaited concurrently via `asyncio.gather`. Returned listings flow through `IngestService`.
2. **Watch sweep** — for each `is_high_priority=true` row in `console.parts_watches`, the same adapters are run with `query=<saved query>`. Results update the watch row's `last_crawled_at` and `match_count`.

Live-search (`/parts/live-search` in the console) takes a third path: it calls `parts-watch search --query <q> --bike-key <k>`, which shells out and reuses the same crawl orchestrator with `query` set.

### Adding a new adapter

The minimal recipe:

1. Create `motorcycle_parts_watcher/adapters/<name>.py` exposing a class with `name`, `enabled`, and `async fetch(self, bike, query=None) -> list[NormalizedListing]`.
2. Export it from `motorcycle_parts_watcher/adapters/__init__.py`.
3. Add a `<NAME>_ENABLED` field to `motorcycle_parts_watcher/config.py::Settings`.
4. Append an instance to `CrawlService.adapters` in `services/crawl.py`.
5. `INSERT INTO watcher.sources (name, type, enabled, base_url) VALUES (...)`.
6. Document it here under §3 or §4.

The adapter should use `motorcycle_parts_watcher/utils/http.py` (`build_async_client`, `AsyncRateLimiter`, `with_retries`) rather than raw `httpx`. This gives every source the shared rate limit and retry/backoff behaviour for free.

### Debugging a silent source

Run `parts-watch crawl --bike <catalog_key>` and look at the `sources={...}` dict in the output line. If your source isn't even listed, check:

```python
# In a Python REPL
from motorcycle_parts_watcher.config import get_settings
s = get_settings()
print(s.<your_field>_enabled)   # gate #1
```

```sql
SELECT enabled FROM watcher.sources WHERE name = '<your_name>';   -- gate #2
```

If it's listed with `0` rows, the adapter ran but returned nothing — add `logging.debug(...)` to the adapter's `_parse_*` and run with `LOG_LEVEL=DEBUG` to see what it saw.

---

## 7. Query translation

A user typing `"exhaust"` would previously hit zero rows on Webike TW (Chinese titles), Yahoo Auctions JP (Japanese titles), and Monotaro JP (Japanese titles). To fix this, every `query` flowing through `CrawlService._crawl_one` is translated per-adapter into that adapter's preferred language *before* dispatch.

### How it works

Each adapter declares a `preferred_query_lang` class attribute:

| Adapter | `preferred_query_lang` |
|---|---|
| `EbayAdapter` | `"en"` |
| `WebikeAdapter` | `"zh-TW"` |
| `YahooAuctionsAdapter` | `"ja"` |
| `BuyeeAdapter` | `"ja"` |
| `MonotaroAdapter` | `"ja"` |
| `ManualSearchAdapter` | `None` (preserves the user's literal query) |
| All stubs | `None` |

The orchestrator detects the *source* language of the user's query via a character-class heuristic (hiragana/katakana → `ja`; han-only → `zh-TW`; otherwise `en`), then translates the query into each adapter's preferred language using a curated dictionary in `motorcycle_parts_watcher/utils/i18n.py`.

### What gets translated

A small parts-vocabulary dictionary (~40 entries: exhaust/brake/fairing/oil filter/spark plug/...) covers the most common queries. Multi-word phrases match greedily (`"oil filter"` → `"オイルフィルター"`, not `"oil"` + `"filter"`). Unknown tokens — brand names, part numbers, the bike's own model name — pass through verbatim, which is the right behaviour since proper nouns are universal.

### Verified

A live-search for `"exhaust"` against the Katana now ingests **92 rows** (vs. 1 before): Yahoo Auctions 50, Monotaro 40, Webike 1, manual_search 1. Identical results when the user types `"排氣管"` or `"マフラー"`.

### Extending the dictionary

Append a row to `PARTS_DICT` in `motorcycle_parts_watcher/utils/i18n.py`:

```python
{"en": "kickstand", "zh-TW": "側柱", "ja": "サイドスタンド"},
```

No code changes needed — the index is rebuilt at module import.

### Translating to another language

To add (say) German for `EBAY_DE`-specific routing:

1. Add `"de"` columns to `PARTS_DICT` rows.
2. Update `_INDEX` and `_build_index` to include `"de"`.
3. Per-marketplace dispatch in `EbayAdapter._fetch_marketplace` would need to pick the right translation — currently the eBay adapter sends the same English query to every marketplace.
