# Motorcycle Parts Watcher — Database Structure (PostgreSQL)

This document explains the database design used by the project.

- Database: `bike_parts_watcher`
- Schema: `watcher`
- Migration tool: Alembic

---

## 1) Quick ER Diagram

```text
watcher.bikes
  id (PK)
  name, make, model, year, variant, aliases(JSON)

watcher.sources
  id (PK)
  name (UNIQUE), type, base_url, enabled

watcher.listings
  id (PK)
  source_name, source_item_id
  bike_key
  title, description, url (UNIQUE), image_url
  price_amount, price_currency, shipping_amount
  seller_name, seller_country
  condition, category, subcategory, part_number, fitment_text
  listing_status
  first_seen_at, last_seen_at
  raw_json, content_hash
  UNIQUE(source_name, source_item_id)

watcher.listing_snapshots
  id (PK)
  listing_id (FK -> watcher.listings.id, ON DELETE CASCADE)
  checked_at
  price_amount
  availability_status
  raw_json

watcher.alembic_version
  version_num
```

Relationship:

- `watcher.listings (1)` -> `watcher.listing_snapshots (many)`

---

## 2) Table Purpose

## `watcher.bikes`
- Master list of target bikes being tracked.
- `aliases` is JSON (alternative names/search terms).

## `watcher.sources`
- Data source registry (eBay, Yahoo Auctions, Webike, manual search).
- `enabled` controls whether a source is active.

## `watcher.listings`
- Main current-state table for each discovered listing.
- Stores latest known status, price, seller info, and classification.
- Deduplication keys:
  - (`source_name`, `source_item_id`)
  - `url`
  - `content_hash` (indexed signal)

## `watcher.listing_snapshots`
- History table. One row per crawl check.
- Preserves price/availability changes over time.

## `watcher.alembic_version`
- Internal migration state table managed by Alembic.

---

## 3) Important Indexes and Constraints

In `watcher.listings`:

- Unique constraints:
  - `uq_listings_url` on `url`
  - `uq_listings_source_item` on (`source_name`, `source_item_id`)
- Indexes:
  - `source_name`
  - `source_item_id`
  - `bike_key`
  - `category`
  - `part_number`
  - `content_hash`

In `watcher.listing_snapshots`:

- Index on `listing_id`

---

## 4) Practical SQL Examples

## A. List tables in `watcher` schema

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'watcher'
ORDER BY tablename;
```

## B. Count listings by bike

```sql
SELECT bike_key, COUNT(*) AS listing_count
FROM watcher.listings
GROUP BY bike_key
ORDER BY listing_count DESC;
```

## C. Count listings by category

```sql
SELECT category, COUNT(*) AS listing_count
FROM watcher.listings
GROUP BY category
ORDER BY listing_count DESC;
```

## D. Latest 20 listings seen

```sql
SELECT id, bike_key, source_name, title, price_amount, price_currency, last_seen_at
FROM watcher.listings
ORDER BY last_seen_at DESC
LIMIT 20;
```

## E. Price history for one listing

```sql
SELECT s.checked_at, s.price_amount, s.availability_status
FROM watcher.listing_snapshots s
WHERE s.listing_id = 123
ORDER BY s.checked_at DESC;
```

## F. Find likely duplicates by same content hash

```sql
SELECT content_hash, COUNT(*) AS cnt
FROM watcher.listings
GROUP BY content_hash
HAVING COUNT(*) > 1
ORDER BY cnt DESC;
```

## G. Listings from a specific source (eBay)

```sql
SELECT id, source_item_id, title, url, price_amount, price_currency
FROM watcher.listings
WHERE source_name = 'ebay'
ORDER BY last_seen_at DESC
LIMIT 50;
```

## H. Listings with no category match

```sql
SELECT id, bike_key, title, source_name
FROM watcher.listings
WHERE category = 'unknown'
ORDER BY last_seen_at DESC;
```

## I. Snapshot volume per day

```sql
SELECT DATE(checked_at) AS day, COUNT(*) AS snapshots
FROM watcher.listing_snapshots
GROUP BY DATE(checked_at)
ORDER BY day DESC;
```

---

## 5) Useful psql Commands

If you use `psql`:

```sql
\dn                 -- list schemas
\dt watcher.*       -- list tables in watcher schema
\d watcher.listings -- describe table
\d watcher.listing_snapshots
```

