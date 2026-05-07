"""Webike TW — keyword search via headless Chromium (Playwright).

Complements WebikeAdapter (which scrapes static per-bike model pages) by
driving Webike's JS-rendered /search endpoint. This returns the full catalog
result set for a keyword — far more results than the ~20-30 products on any
single /md/{ID} model page.

Cloudflare note
---------------
webike.tw is behind Cloudflare. Requests originating from data-center IPs
(VPS, cloud providers) hit the Cloudflare challenge page and return no data.
Set WEBIKE_PROXY_URL to a residential proxy (e.g. socks5://user:pass@host:port
or http://user:pass@host:port) so Cloudflare treats the request as coming from
a browser on a consumer ISP.

    WEBIKE_PROXY_URL=socks5://myuser:mypass@proxy.example.com:1080

Without a proxy, the adapter logs a one-line WARNING and returns [].
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import parse_decimal

logger = logging.getLogger(__name__)

WEBIKE_BASE = "https://www.webike.tw"
MAX_PAGES = 5
_BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class WebikeSearchAdapter:
    """Webike TW full keyword search via Playwright headless Chromium.

    Drives Webike's JS-rendered /search?q=… endpoint and paginates up to
    MAX_PAGES pages. Requires WEBIKE_PROXY_URL (residential) to pass
    Cloudflare's bot-protection when running from a data-center IP.
    """

    name = "webike_search"
    preferred_query_lang: str | None = "zh-TW"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_search_enabled
        self._proxy_url = settings.webike_proxy_url or None

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("webike_search: playwright not installed; run `playwright install chromium --with-deps`")
            return []

        search_query = query or bike.search_terms[0]
        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        launch_kwargs: dict = {"headless": True, "args": _BROWSER_ARGS}
        if self._proxy_url:
            launch_kwargs["proxy"] = {"server": self._proxy_url}

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(**launch_kwargs)
                try:
                    for page_num in range(1, MAX_PAGES + 1):
                        page_results, has_next = await self._fetch_page(
                            browser, search_query, bike, page_num, seen_ids
                        )
                        results.extend(page_results)
                        if not page_results or not has_next:
                            break
                finally:
                    await browser.close()
        except Exception as exc:
            logger.warning("webike_search fetch failed for %s: %s", bike.catalog_key, exc)

        return results

    async def _fetch_page(self, browser, search_query: str, bike: BikeRef, page_num: int, seen_ids: set[str]) -> tuple[list[NormalizedListing], bool]:
        url = f"{WEBIKE_BASE}/search?q={quote(search_query)}"
        if page_num > 1:
            url += f"&page={page_num}"

        page = await browser.new_page(
            user_agent=_UA,
            locale="zh-TW",
            extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"},
        )
        try:
            await page.goto(url, wait_until="load", timeout=30_000)
            # Give JS up to 10s to render product cards after DOM load
            try:
                await page.wait_for_selector("meta[itemprop='price']", timeout=10_000)
            except Exception:
                pass
            html = await page.content()
        except Exception as exc:
            logger.warning("webike_search: page load failed (page=%d): %s", page_num, exc)
            return [], False
        finally:
            await page.close()

        if _is_cloudflare_challenge(html):
            proxy_hint = "" if self._proxy_url else " — set WEBIKE_PROXY_URL to a residential proxy to bypass"
            logger.warning("webike_search: Cloudflare challenge page returned for %s%s", bike.catalog_key, proxy_hint)
            return [], False

        listings = _parse_results(html, bike, search_query, seen_ids)
        has_next = _has_next_page(html, page_num)
        return listings, has_next


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _is_cloudflare_challenge(html: str) -> bool:
    return "challenges.cloudflare.com" in html or "Just a moment" in html or "請稍候" in html


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


def _has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    next_page = current_page + 1
    if soup.select_one(f"a[href*='page={next_page}']"):
        return True
    if soup.select_one("a[rel='next']"):
        return True
    for el in soup.select(".pagination a, .pagination li:not(.disabled) a"):
        if el.get_text(strip=True) in ("›", "»", ">", "Next", "次頁", "下一頁"):
            return True
    return False


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
