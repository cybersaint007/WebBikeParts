from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


class ManualSearchAdapter:
    name = "manual_search"
    # None = preserve the user's literal query so the watch list shows what was typed
    preferred_query_lang: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.manual_search_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        data_file = Path("manual_listings.json")
        if data_file.exists():
            return self._from_file(bike, data_file)
        return self._query_seeds(bike, query)

    def _query_seeds(self, bike: BikeRef, query: str | None) -> list[NormalizedListing]:
        terms = bike.search_terms
        if query:
            terms = [f"{t} {query}" for t in terms]
        # Make the seed id query-aware so the same bike + different queries each get
        # their own listing row (otherwise IngestService dedup by source_item_id keeps
        # the original title unchanged on subsequent ingests).
        q_tag = hashlib.sha1((query or "").encode("utf-8")).hexdigest()[:8] if query else "base"
        results: list[NormalizedListing] = []
        for idx, term in enumerate(terms, start=1):
            search_url = f"https://www.google.com/search?q={quote_plus(f'{term} motorcycle parts')}"
            label = f"Manual search query: {term}"
            results.append(
                NormalizedListing(
                    source_name=self.name,
                    source_item_id=f"{bike.catalog_key}-seed-{q_tag}-{idx}",
                    bike_key=bike.catalog_key,
                    title=label,
                    description="Fallback search seed",
                    url=search_url,
                    listing_status="manual_seed",
                    raw_json={"query": term, "seed": True},
                )
            )
        return results

    def _from_file(self, bike: BikeRef, data_file: Path) -> list[NormalizedListing]:
        import json

        payload = json.loads(data_file.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = payload.get(bike.catalog_key, [])
        listings: list[NormalizedListing] = []
        for row in rows:
            listings.append(
                NormalizedListing(
                    source_name=self.name,
                    source_item_id=row.get("source_item_id"),
                    bike_key=bike.catalog_key,
                    title=row.get("title", "Manual Listing"),
                    description=row.get("description"),
                    url=row["url"],
                    image_url=row.get("image_url"),
                    condition=row.get("condition"),
                    seller_name=row.get("seller_name"),
                    seller_country=row.get("seller_country"),
                    listing_status=row.get("listing_status", "active"),
                    raw_json=row,
                )
            )
        return listings
