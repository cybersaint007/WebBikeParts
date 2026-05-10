"""Old Bike Barn adapter — Shopify storefront for vintage Japanese parts.

Old Bike Barn (oldbikebarn.com) sells vintage OEM and aftermarket parts for
'60s–'90s Honda / Yamaha / Suzuki / Kawasaki motorcycles. Because it's hosted
on Shopify, the public catalog is reachable via two JSON endpoints — no HTML
scraping, no Cloudflare WAF games:

  GET /collections.json?limit=250&page=N            — all collections
  GET /collections/{handle}/products.json?limit=250&page=N
                                                    — products in one collection

Bike-keyed collections look like::

    handle: suzuki-gs1100-oem-aftermarket-parts
    title : "Suzuki GS1100 Parts (1980–1983) – OEM & Aftermarket Motorcycle Parts"

We discover all collections on first use (about 4 pages × 250 = ~1000),
parse their titles into ``(make, model)`` tuples, and cache for 24 h. At
fetch time we resolve a :class:`BikeRef` to one or more handles and page
through each collection's products.

**Year filtering is deliberately permissive.** A "Suzuki GS1100 Parts
(1980–1983)" collection covers every GS1100 sub-variant; per-product
fitment ("Suzuki 80-81 GS1100 Engine Gasket Set") goes into ``fitment_text``
and the search-side ILIKE handles refinement. Filtering at adapter time
would silently drop products whose titles use the dealer's year shorthand.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import (
    AsyncRateLimiter,
    build_async_client,
    parse_decimal,
    with_retries,
)


logger = logging.getLogger(__name__)

OBB_BASE = "https://oldbikebarn.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

# Recognised makes — limits parser scope so generic part-category collections
# ("Air & Oil Filters", "Oil Pumps – 2135") don't get false-matched as bikes.
_MAKES = ("Honda", "Yamaha", "Suzuki", "Kawasaki")
_MAKE_ALT = "|".join(_MAKES)

# Pattern: "<Make> <model section> Parts ..."
# - model section can include spaces ("CMX250 Rebel 250"), `&` joins
#   ("CB350 & CL350"), and an optional pre-Parts year-in-parens ("CB1000C (1983)").
_TITLE_RE = re.compile(
    rf"^\s*(?P<make>{_MAKE_ALT})\s+(?P<rest>.+?)\s+Parts\b",
    re.IGNORECASE,
)
_TRAILING_YEAR_RE = re.compile(r"\s*\(\s*\d{4}(?:\s*[-–]\s*\d{4})?\s*\)\s*$")

CACHE_TTL_SECONDS = 24 * 60 * 60


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class OldBikeBarnAdapter:
    name = "old_bike_barn"
    preferred_query_lang: str | None = "en"

    # Class-scoped cache so a worker process reuses the index across jobs.
    _index: "_CollectionIndex | None" = None
    _index_lock: asyncio.Lock | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.old_bike_barn_enabled
        # Shopify is generous; cap at 1 rps regardless of the global limit so we
        # stay polite even when other adapters bump HTTP_RATE_LIMIT_PER_SECOND.
        polite = min(1.0, settings.http_rate_limit_per_second)
        self._limiter = AsyncRateLimiter(polite)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        try:
            index = await self._get_index()
        except Exception as exc:
            logger.warning("old_bike_barn collection index fetch failed: %s", exc)
            return []

        handles = index.handles_for_bike(bike)
        if not handles:
            logger.info(
                "old_bike_barn: no collection match for %s/%s",
                bike.make,
                bike.model,
            )
            return []

        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()
        for handle in handles:
            try:
                products = await self._fetch_collection(handle)
            except Exception as exc:
                logger.warning(
                    "old_bike_barn: collection %s fetch failed: %s", handle, exc
                )
                continue
            for prod in products:
                pid = str(prod.get("id") or "")
                if not pid or pid in seen_ids:
                    continue
                listing = self._normalize(prod, bike, handle, query)
                if listing is None:
                    continue
                seen_ids.add(pid)
                results.append(listing)
        return results

    # --- Index management ------------------------------------------------

    async def _get_index(self) -> "_CollectionIndex":
        cls = type(self)
        if cls._index_lock is None:
            cls._index_lock = asyncio.Lock()
        async with cls._index_lock:
            if cls._index is None or cls._index.is_stale():
                cls._index = await _CollectionIndex.build(
                    settings=self.settings, limiter=self._limiter
                )
            return cls._index

    # --- HTTP ------------------------------------------------------------

    async def _fetch_collection(self, handle: str) -> list[dict[str, Any]]:
        """Page through `/collections/{handle}/products.json` until empty."""
        all_products: list[dict[str, Any]] = []
        page = 1
        while True:
            url = (
                f"{OBB_BASE}/collections/{handle}/products.json"
                f"?limit=250&page={page}"
            )
            data = await _fetch_json(url, self.settings, self._limiter)
            products = data.get("products") or []
            all_products.extend(products)
            if len(products) < 250:
                break
            page += 1
            if page > 20:
                logger.warning(
                    "old_bike_barn: collection %s exceeded 20 pages, stopping",
                    handle,
                )
                break
        return all_products

    # --- Normalization ---------------------------------------------------

    def _normalize(
        self,
        prod: dict[str, Any],
        bike: BikeRef,
        handle: str,
        query: str | None,
    ) -> NormalizedListing | None:
        title = (prod.get("title") or "").strip()
        product_handle = prod.get("handle") or ""
        if not title or not product_handle:
            return None

        variants = prod.get("variants") or []
        v0 = variants[0] if variants else {}
        price = parse_decimal(v0.get("price"))
        available = bool(v0.get("available"))
        sku = (v0.get("sku") or "").strip() or None

        images = prod.get("images") or []
        first_image = images[0] if images else None
        image_url = (first_image or {}).get("src") if isinstance(first_image, dict) else None

        tags = prod.get("tags") or []
        tag_str = ", ".join(t for t in tags if isinstance(t, str)) if tags else ""
        fitment_bits = [title]
        if tag_str:
            fitment_bits.append(tag_str)
        fitment_text = " | ".join(fitment_bits)[:1000]

        return NormalizedListing(
            source_name=self.name,
            source_item_id=str(prod.get("id")),
            bike_key=bike.catalog_key,
            title=title[:480],
            description=prod.get("body_html") or None,
            url=f"{OBB_BASE}/products/{product_handle}",
            image_url=image_url,
            price_amount=price,
            price_currency="USD",
            condition="new",
            category=(prod.get("product_type") or "unknown") or "unknown",
            part_number=sku,
            fitment_text=fitment_text,
            listing_status="active" if available else "out_of_stock",
            raw_json={
                "collection_handle": handle,
                "vendor": prod.get("vendor"),
                "tags": tags,
                "search_query": query,
            },
        )


# ---------------------------------------------------------------------------
# Collection index (private)
# ---------------------------------------------------------------------------


class _CollectionIndex:
    """Resolves a ``BikeRef`` to a list of OBB collection handles.

    Built once per process from the paginated ``/collections.json`` feed and
    refreshed every :data:`CACHE_TTL_SECONDS`. Lookup is case-insensitive on
    ``(make, model)`` plus ``(make, head_token_of_model)``.
    """

    def __init__(
        self,
        by_key: dict[tuple[str, str], list[str]],
        built_at: float,
        collections_count: int,
    ) -> None:
        self._by_key = by_key
        self._built_at = built_at
        self._collections_count = collections_count

    def is_stale(self) -> bool:
        return (time.time() - self._built_at) > CACHE_TTL_SECONDS

    def handles_for_bike(self, bike: BikeRef) -> list[str]:
        make = (bike.make or "").lower().strip()
        if not make:
            return []
        whole = (bike.model or "").lower().strip()
        if whole:
            handles = self._by_key.get((make, whole))
            if handles:
                return handles
        # Fall back to first model token (e.g. "GSX1100S" from "GSX1100S KATANA").
        for tok in (bike.model or "").split():
            handles = self._by_key.get((make, tok.lower()))
            if handles:
                return handles
        return []

    @classmethod
    async def build(
        cls, *, settings: Settings, limiter: AsyncRateLimiter
    ) -> "_CollectionIndex":
        all_collections: list[dict[str, Any]] = []
        page = 1
        while True:
            url = f"{OBB_BASE}/collections.json?limit=250&page={page}"
            data = await _fetch_json(url, settings, limiter)
            cols = data.get("collections") or []
            all_collections.extend(cols)
            if len(cols) < 250:
                break
            page += 1
            if page > 8:
                break

        by_key: dict[tuple[str, str], list[str]] = {}
        for col in all_collections:
            handle = col.get("handle") or ""
            title = col.get("title") or ""
            if not handle or not title:
                continue
            for make, model in parse_collection_title(title):
                key_whole = (make.lower(), model.lower())
                by_key.setdefault(key_whole, []).append(handle)
                head = model.split()[0] if model.split() else ""
                if head and head.lower() != model.lower():
                    by_key.setdefault((make.lower(), head.lower()), []).append(handle)
        # Dedupe handles per key while preserving order.
        for k in list(by_key.keys()):
            seen: set[str] = set()
            deduped: list[str] = []
            for v in by_key[k]:
                if v in seen:
                    continue
                seen.add(v)
                deduped.append(v)
            by_key[k] = deduped

        logger.info(
            "old_bike_barn: indexed %d collections, %d bike keys",
            len(all_collections),
            len(by_key),
        )
        return cls(
            by_key=by_key,
            built_at=time.time(),
            collections_count=len(all_collections),
        )


def parse_collection_title(title: str) -> list[tuple[str, str]]:
    """Extract ``(make, model)`` tuples from an OBB collection title.

    Handles the shapes seen in production::

        "Suzuki GS1100 Parts (1980–1983) – OEM & ..."        → [(Suzuki, GS1100)]
        "Honda CB350 & CL350 Parts (1968–1973) – ..."        → [(Honda, CB350), (Honda, CL350)]
        "Honda CB1000C (1983) Parts – Vintage ..."           → [(Honda, CB1000C)]
        "Honda CB1100F Parts (1983) – OEM & ..."             → [(Honda, CB1100F)]
        "Honda CMX250 Rebel 250 Parts (1985-2016)"           → [(Honda, CMX250 Rebel 250)]
        "Honda CBR600 Parts | CBR600F Hurricane, ..."        → [(Honda, CBR600)]

    Returns ``[]`` for non-bike titles ("Oil Pumps – 2135", "Honda CB750:
    Electrical Parts" — colon-prefix is treated as a category title, not a
    model).
    """
    # Reject category-style titles where a colon precedes "Parts".
    head = title.split("Parts", 1)[0]
    if ":" in head:
        return []
    m = _TITLE_RE.match(title)
    if not m:
        return []
    make = m.group("make").title()
    rest = m.group("rest").strip()
    # Strip a trailing "(YYYY)" or "(YYYY-YYYY)" / "(YYYY–YYYY)" if it was the
    # only thing between the model and "Parts" (e.g. "CB1000C (1983) Parts").
    rest = _TRAILING_YEAR_RE.sub("", rest).strip()
    if not rest:
        return []
    if " & " in rest:
        return [(make, p.strip()) for p in rest.split(" & ") if p.strip()]
    return [(make, rest)]


async def _fetch_json(
    url: str, settings: Settings, limiter: AsyncRateLimiter
) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with build_async_client(settings) as client:
        await limiter.wait()
        response = await with_retries(
            lambda: client.get(url, headers=headers),
            retries=settings.http_retries,
            backoff_seconds=settings.http_retry_backoff_seconds,
        )
    return response.json()
