"""Webike TW — keyword search via Google CSE + category page scraping.

Strategy
--------
1. Playwright drives webike.tw/search?q=… and waits for Google Custom Search
   to inject .gsc-result elements into the page.
2. Category-page URLs extracted from those CSE results are fetched with plain
   httpx — they are server-rendered and contain the same product-card structure
   (meta[itemprop='price'] + /sd/ anchors) as the per-bike model pages.

This complements WebikeAdapter (per-bike /md/ model pages) by adding
keyword-driven category coverage.

Cloudflare note
---------------
The initial search page requires Playwright to execute Google CSE JavaScript.
Category pages (webike.tw/parts/ca/…) are server-rendered and do not need a
proxy from a residential IP. On data-center IPs the search step may return a
Cloudflare challenge; set WEBIKE_PROXY_URL to a residential proxy.
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
MAX_CATEGORY_URLS = 5
_BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class WebikeSearchAdapter:
    """Webike TW keyword search via Google CSE + category page scraping.

    Uses Playwright to get CSE search results, then httpx to fetch product
    listings from the category pages those results link to.
    """

    name = "webike_search"
    preferred_query_lang: str | None = "zh-TW"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_search_enabled
        self._proxy_url = settings.webike_proxy_url or None
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        search_query = query or bike.search_terms[0]

        category_urls = await self._get_category_urls(search_query, bike)
        if not category_urls:
            return []

        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        async with build_async_client(self.settings) as client:
            for cat_url in category_urls[:MAX_CATEGORY_URLS]:
                await self._limiter.wait()
                page_results = await self._fetch_category(client, cat_url, bike, search_query, seen_ids)
                results.extend(page_results)

        return results

    async def _get_category_urls(self, search_query: str, bike: BikeRef) -> list[str]:
        """Use Playwright to load the CSE search page and extract category URLs."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("webike_search: playwright not installed; run `playwright install chromium --with-deps`")
            return []

        launch_kwargs: dict = {"headless": True, "args": _BROWSER_ARGS}
        if self._proxy_url:
            launch_kwargs["proxy"] = {"server": self._proxy_url}

        url = f"{WEBIKE_BASE}/search?q={quote(search_query)}"
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(**launch_kwargs)
                try:
                    page = await browser.new_page(
                        user_agent=_UA,
                        locale="zh-TW",
                        extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
                    )
                    await page.goto(url, wait_until="load", timeout=30_000)
                    try:
                        await page.wait_for_selector(".gsc-result", timeout=10_000)
                    except Exception:
                        pass
                    html = await page.content()
                finally:
                    await browser.close()
        except Exception as exc:
            logger.warning("webike_search: search page failed for %s: %s", bike.catalog_key, exc)
            return []

        if _is_cloudflare_challenge(html):
            proxy_hint = "" if self._proxy_url else " — set WEBIKE_PROXY_URL to a residential proxy to bypass"
            logger.warning("webike_search: Cloudflare challenge for %s%s", bike.catalog_key, proxy_hint)
            return []

        return _extract_category_urls(html)

    async def _fetch_category(
        self,
        client,
        cat_url: str,
        bike: BikeRef,
        search_query: str,
        seen_ids: set[str],
    ) -> list[NormalizedListing]:
        try:
            response = await with_retries(
                lambda: client.get(cat_url, headers={"User-Agent": _UA}),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
        except Exception as exc:
            logger.warning("webike_search: category fetch failed (%s): %s", cat_url, exc)
            return []
        return _parse_results(response.text, bike, search_query, seen_ids)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _is_cloudflare_challenge(html: str) -> bool:
    return "challenges.cloudflare.com" in html or "Just a moment" in html or "請稍候" in html


def _extract_category_urls(html: str) -> list[str]:
    """Extract unique webike.tw category URLs from Google CSE result elements."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    urls: list[str] = []
    for result in soup.select(".gsc-result"):
        for a in result.select("a[href]"):
            href = a.get("href", "")
            if "webike.tw" not in href:
                continue
            clean = re.sub(r"\?.*", "", href)  # strip Google tracking params
            if clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)
                break  # one URL per CSE result
    return urls


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
    """Walk up from a price <meta> to the nearest ancestor that contains a /sd/ anchor."""
    node = price_meta
    for _ in range(8):
        node = node.parent
        if node is None:
            return None
        if node.select_one("a[href*='/sd/']"):
            return node
    return None


def _best_image(container) -> str | None:
    # Product image on Webike lives in a sibling outside item__body, so walk up.
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
    # Prefer img alt > element title attr > visible text.
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
