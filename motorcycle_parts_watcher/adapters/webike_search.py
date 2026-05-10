"""Webike TW — keyword search via /parts?q= (server-rendered).

Strategy
--------
GET https://www.webike.tw/parts?q=<query> and paginate. The results page is
server-rendered (no Playwright needed) and uses the same product-card structure
(meta[itemprop='price'] + /sd/ anchors) as the per-bike model pages.

The query is the translated keyword supplied by the producer (watch sweeps) or,
for a plain bike sweep, the first entry of BikeRef.search_terms (make + model +
year). This finds products that mention the bike model in title/fitment even if
they are not associated with the model page in webike's catalog.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

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

WEBIKE_BASE = "https://www.webike.tw"
SEARCH_URL = f"{WEBIKE_BASE}/parts"
MAX_PAGES = 50
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class WebikeSearchAdapter:
    """Webike TW keyword search via /parts?q= (plain httpx, no Playwright)."""

    name = "webike_search"
    preferred_query_lang: str | None = "zh-TW"
    is_keyword_search: bool = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_search_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        # Anchor to the model name only (no make, no year) — adding the brand
        # name or year range causes webike.tw AND-matching to drop most results.
        # For keyword sweeps, append the translated keyword to narrow further.
        search_query = f"{bike.model} {query}".strip() if query else bike.model
        headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}

        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        async with build_async_client(self.settings) as client:
            for page_num in range(1, MAX_PAGES + 1):
                params = {"q": search_query}
                if page_num > 1:
                    params["page"] = str(page_num)

                try:
                    response = await with_retries(
                        lambda p=params: client.get(SEARCH_URL, params=p, headers=headers),
                        retries=self.settings.http_retries,
                        backoff_seconds=self.settings.http_retry_backoff_seconds,
                    )
                    response.raise_for_status()
                except Exception as exc:
                    logger.warning("webike_search: fetch failed (page %d): %s", page_num, exc)
                    break

                page_results = _parse_results(response.text, bike, search_query, seen_ids)
                results.extend(page_results)

                if not page_results or not _has_next_page(response.text, page_num):
                    break

                await self._limiter.wait()

        logger.debug(
            "webike_search: %s query=%r → %d results",
            bike.catalog_key, search_query, len(results),
        )
        return results


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.select_one(f"a[href*='page={current_page + 1}']"))


def _parse_results(html: str, bike: BikeRef, search_query: str, seen_ids: set[str]) -> list[NormalizedListing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[NormalizedListing] = []

    for price_meta in soup.select("meta[itemprop='price']"):
        container = _find_product_container(price_meta)
        if container is None:
            continue
        anchor = container.select_one("a[href*='/sd/']")
        if anchor is None:
            continue
        absolute_url = urljoin(WEBIKE_BASE, anchor.get("href", ""))
        item_id = _extract_id(absolute_url)
        if not item_id or item_id in seen_ids:
            continue

        title = _best_title(container)
        if not title or len(title) < 3:
            continue

        image_url = _best_image(container)
        price_amount = parse_decimal(price_meta.get("content"))
        currency_meta = container.select_one("meta[itemprop='priceCurrency']")
        currency = currency_meta.get("content") if currency_meta else None

        seen_ids.add(item_id)
        results.append(
            NormalizedListing(
                source_name="webike_search",
                source_item_id=item_id,
                bike_key=bike.catalog_key,
                title=title,
                description=None,
                url=absolute_url,
                image_url=image_url,
                price_amount=price_amount,
                price_currency=currency,
                listing_status="active",
                raw_json={"search_query": search_query},
            )
        )

    return results


def _find_product_container(price_meta):
    node = price_meta
    for _ in range(8):
        node = node.parent
        if node is None:
            return None
        if node.select_one("a[href*='/sd/']"):
            return node
    return None


def _best_image(container) -> str | None:
    node = container
    for _ in range(4):
        if node is None:
            break
        for img in node.select("img"):
            for attr in ("src", "data-src", "data-lazy-src", "data-original"):
                v = img.get(attr)
                if v and not v.startswith("data:"):
                    if v.startswith("//"):
                        v = "https:" + v
                    return v
        node = node.parent
    return None


def _best_title(container) -> str:
    for sel in ("img", ".product-name", ".name", "[class*='title']"):
        el = container.select_one(sel)
        if el is None:
            continue
        for attr in ("alt", "title"):
            v = el.get(attr) if hasattr(el, "get") else None
            if v and len(v.strip()) >= 3:
                return v.strip()[:480]
        txt = el.get_text(strip=True)
        if txt and len(txt) >= 3:
            return txt[:480]
    if title := container.get("title"):
        return title.strip()[:480]
    return container.get_text(" ", strip=True)[:480]


def _extract_id(url: str) -> str | None:
    m = re.search(r"/sd/([0-9A-Za-z_-]+)", url)
    return m.group(1) if m else None
