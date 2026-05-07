-- Data migration: merge suzuki-katana-1100-1990 into suzuki-gsx1100s-katana-1990-1993
--
-- Background: admin@example.com had the manually-seeded catalog row (id=1,
-- catalog_key=suzuki-katana-1100-1990, model="Katana 1100") while
-- james.lee@fincosoft.com had the Webike-scraped row (id=4877,
-- catalog_key=suzuki-gsx1100s-katana-1990-1993) for the same physical bike.
-- This caused each user to see only the listings crawled under their own key
-- (211 vs 15). This migration retags all legacy rows to the canonical scraped
-- key and points admin's user_bikes/parts_watches at the same catalog row.
--
-- Applied: 2026-05-07

BEGIN;

-- Re-tag listings crawled under the legacy key (211 rows).
UPDATE watcher.listings
   SET bike_key = 'suzuki-gsx1100s-katana-1990-1993'
 WHERE bike_key = 'suzuki-katana-1100-1990';

-- Re-tag historical crawl_job rows for consistency.
UPDATE watcher.crawl_jobs
   SET bike_catalog_key = 'suzuki-gsx1100s-katana-1990-1993'
 WHERE bike_catalog_key = 'suzuki-katana-1100-1990';

-- Point admin's My Bikes entry at the canonical catalog row.
UPDATE console.user_bikes
   SET bike_catalog_id = 4877
 WHERE user_id = (SELECT id FROM console.users WHERE email = 'admin@example.com')
   AND bike_catalog_id = 1;

-- Point admin's watch list entries at the canonical catalog row.
UPDATE console.parts_watches
   SET bike_catalog_id = 4877
 WHERE user_id = (SELECT id FROM console.users WHERE email = 'admin@example.com')
   AND bike_catalog_id = 1;

COMMIT;
