"""Webike TW — global category tree crawler.

Complements the webike adapter (which scrapes model pages) by walking the
global category tree (/parts/ca/…) without a model filter. This finds products
that are categorised by part type only and have no bike-model association on
webike.tw, which the model-page scraper cannot reach.

Strategy
--------
1. Fetch the bike's model page (/parts/md/{id}) to discover which category
   codes are relevant to this model (e.g. 1000=改裝零件, 3000=騎士用品, …).
2. Walk up to 3 levels of the category tree using the model-filtered pages
   (e.g. /parts/md/679/ca/1000 → /parts/md/679/ca/1000-1059 → leaf codes).
3. For each leaf code, fetch the GLOBAL version (/parts/ca/{code}) without
   the model filter and paginate to collect all products, including those with
   no model association.

This gives coverage of both model-associated products (already found by the
webike adapter) and globally-listed products not tied to a specific model.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MAX_CAT_PAGES = 30  # safety cap per leaf category page


class WebikeCatAdapter:
    """Webike TW global category tree crawler.

    Discovers relevant category codes from the model page navigation, then
    scrapes the global (non-model-filtered) version of each leaf category.
    """

    name = "webike_cat"
    preferred_query_lang: str | None = "zh-TW"
    is_keyword_search: bool = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_cat_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        if not bike.webike_url:
            logger.info("webike_cat: bike %s has no webike_url; skipping", bike.catalog_key)
            return []

        # Use base model URL (strip kt/ year variant) for broadest category discovery
        parts_url = bike.webike_url.replace("/md/", "/parts/md/", 1)
        model_base = re.sub(r"/kt/\d+.*", "", parts_url).rstrip("/")

        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        try:
            async with build_async_client(self.settings) as client:
                leaf_codes = await self._discover_leaves(client, model_base, headers)
                logger.debug("webike_cat: %s — %d leaf categories", bike.catalog_key, len(leaf_codes))
                for code in leaf_codes:
                    cat_results = await self._scrape_category(client, code, bike, seen_ids, headers)
                    results.extend(cat_results)
        except Exception as exc:
            logger.warning("webike_cat fetch failed for %s: %s", bike.catalog_key, exc)

        return results

    async def _discover_leaves(self, client, model_base: str, headers: dict) -> list[str]:
        """Walk model-page category navigation up to 4 levels; return leaf codes."""
        leaves: list[str] = []

        html = await self._fetch_html(client, model_base, headers)
        if not html:
            return []
        l1_codes = _extract_child_codes(html, "", model_base)

        for l1 in l1_codes:
            await self._limiter.wait()
            html = await self._fetch_html(client, f"{model_base}/ca/{l1}", headers)
            if not html:
                continue
            l2_codes = _extract_child_codes(html, l1, model_base)
            if not l2_codes:
                leaves.append(l1)
                continue

            for l2 in l2_codes:
                await self._limiter.wait()
                html = await self._fetch_html(client, f"{model_base}/ca/{l2}", headers)
                if not html:
                    continue
                l3_codes = _extract_child_codes(html, l2, model_base)
                if not l3_codes:
                    leaves.append(l2)
                    continue

                for l3 in l3_codes:
                    await self._limiter.wait()
                    html = await self._fetch_html(client, f"{model_base}/ca/{l3}", headers)
                    if not html:
                        continue
                    l4_codes = _extract_child_codes(html, l3, model_base)
                    if not l4_codes:
                        leaves.append(l3)
                    else:
                        leaves.extend(l4_codes)

        return leaves

    async def _scrape_category(
        self,
        client,
        code: str,
        bike: BikeRef,
        seen_ids: set[str],
        headers: dict,
    ) -> list[NormalizedListing]:
        """Paginate the global /parts/ca/{code} page and parse all products."""
        base_url = f"{WEBIKE_BASE}/parts/ca/{code}"
        results: list[NormalizedListing] = []

        await self._limiter.wait()
        response = await self._get(client, base_url, headers)
        if response is None:
            return []

        for page_num in range(1, MAX_CAT_PAGES + 1):
            page_results = _parse_results(response.text, bike, seen_ids)
            results.extend(page_results)
            if not page_results or not _has_next_page(response.text, page_num):
                break
            await self._limiter.wait()
            response = await self._get(client, f"{base_url}?page={page_num + 1}", headers)
            if response is None:
                break

        return results

    async def _fetch_html(self, client, url: str, headers: dict) -> str | None:
        try:
            response = await with_retries(
                lambda: client.get(url, headers=headers),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
            response.raise_for_status()
            final = str(response.url)
            if WEBIKE_BASE not in final:
                logger.warning("webike_cat: geo-blocked redirect to %s", final)
                return None
            return response.text
        except Exception as exc:
            logger.warning("webike_cat: fetch failed (%s): %s", url, exc)
            return None

    async def _get(self, client, url: str, headers: dict):
        try:
            response = await with_retries(
                lambda: client.get(url, headers=headers),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            logger.warning("webike_cat: fetch failed (%s): %s", url, exc)
            return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_child_codes(html: str, parent_code: str, model_base: str) -> list[str]:
    """Return category codes that are direct children of parent_code in the nav."""
    soup = BeautifulSoup(html, "lxml")
    codes: list[str] = []
    seen: set[str] = set()
    parent_depth = parent_code.count("-") if parent_code else -1

    # hrefs on the page are path-relative ("/parts/md/679/ca/…"), not absolute
    model_path = model_base.replace(WEBIKE_BASE, "", 1)
    for a in soup.select(f'a[href*="{model_path}/ca/"]'):
        href = a.get("href", "")
        m = re.search(r"/ca/(\d[\d-]*\d|\d)", href)
        if not m:
            continue
        code = m.group(1)
        if code.count("-") != parent_depth + 1:
            continue
        if parent_code and not code.startswith(parent_code + "-"):
            continue
        if code not in seen:
            seen.add(code)
            codes.append(code)

    return codes


def _parse_results(html: str, bike: BikeRef, seen_ids: set[str]) -> list[NormalizedListing]:
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
                source_name="webike_cat",
                source_item_id=item_id,
                bike_key=bike.catalog_key,
                title=title,
                description=None,
                url=absolute_url,
                image_url=image_url,
                price_amount=price_amount,
                price_currency=currency,
                listing_status="active",
                raw_json={},
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


def _has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.select_one(f"a[href*='page={current_page + 1}']"))


def _extract_id(url: str) -> str | None:
    m = re.search(r"/sd/([0-9A-Za-z_-]+)", url)
    return m.group(1) if m else None
