"""Goobike Parts — keyword search via headless Chromium (Playwright).

www.goobike.com/parts/?word=... is a pure SPA with no inline product data.
We drive it with Playwright (networkidle wait) so the JS app can render
its product cards, then parse with BeautifulSoup.

Goobike inventory updates daily, so a nightly crawl is sufficient — the
MAX_PAGES cap is intentionally conservative.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import parse_decimal

logger = logging.getLogger(__name__)

GOOBIKE_BASE = "https://www.goobike.com"
MAX_PAGES = 3
_BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_JPY_STRIP_RE = re.compile(r"[¥円,\s]")

# Ordered list of selectors to try for individual product cards
_ITEM_SELECTORS = [
    "li.parts-list__item",
    ".partsItem",
    "[class*='parts-list'] li",
    "[class*='partsItem']",
    "article[class*='item']",
    "li[class*='item']",
]
_WAIT_SELECTOR = ", ".join(_ITEM_SELECTORS)


class GoobikeAdapter:
    """Goobike Parts search via Playwright headless Chromium."""

    name = "goobike"
    preferred_query_lang: str | None = "ja"
    is_keyword_search: bool = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.goobike_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("goobike: playwright not installed; run `playwright install chromium --with-deps`")
            return []

        search_query = query or bike.search_terms[0]
        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=_BROWSER_ARGS)
                try:
                    context = await browser.new_context(
                        user_agent=_UA,
                        locale="ja-JP",
                        extra_http_headers={"Accept-Language": "ja,en;q=0.9"},
                    )
                    for page_num in range(1, MAX_PAGES + 1):
                        url = f"{GOOBIKE_BASE}/parts/?word={quote(search_query)}"
                        if page_num > 1:
                            url += f"&page={page_num}"

                        page = await context.new_page()
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=30_000)
                            try:
                                await page.wait_for_selector(_WAIT_SELECTOR, timeout=15_000)
                            except Exception:
                                logger.debug(
                                    "goobike: no items on page %d for %s", page_num, bike.catalog_key
                                )
                                break
                            html = await page.content()
                        finally:
                            await page.close()

                        page_listings = _parse_items(html, bike, search_query, seen_ids)
                        if not page_listings:
                            break
                        results.extend(page_listings)
                        if not _has_next(html, page_num):
                            break
                    await context.close()
                finally:
                    await browser.close()
        except Exception as exc:
            logger.warning("goobike: fetch failed for %s: %s", bike.catalog_key, exc)

        logger.info("goobike: %d listings for %s", len(results), bike.catalog_key)
        return results


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_items(
    html: str, bike: BikeRef, search_query: str, seen_ids: set[str]
) -> list[NormalizedListing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[NormalizedListing] = []

    items: list = []
    for selector in _ITEM_SELECTORS:
        items = soup.select(selector)
        if items:
            break

    if not items:
        logger.debug("goobike: no product cards matched any selector in rendered HTML")
        return results

    for item in items:
        anchor = item.select_one("a[href*='/parts/']") or item.select_one("a[href]")
        if not anchor:
            continue
        href = anchor.get("href", "")
        item_id = _extract_item_id(href)
        if not item_id or item_id in seen_ids:
            continue

        title = _extract_title(item)
        if not title:
            continue

        url = href if href.startswith("http") else GOOBIKE_BASE + href
        seen_ids.add(item_id)
        results.append(
            NormalizedListing(
                source_name="goobike",
                source_item_id=item_id,
                bike_key=bike.catalog_key,
                title=title,
                url=url,
                image_url=_extract_image(item),
                price_amount=_extract_price(item),
                price_currency="JPY",
                condition=_extract_condition(item),
                listing_status="active",
                raw_json={"search_query": search_query},
            )
        )

    return results


def _extract_item_id(href: str) -> str | None:
    # Try to match /parts/detail/{id} or /parts/{id} path patterns
    m = re.search(r"/parts/(?:detail/|item/)?([A-Za-z0-9_-]{3,})", href)
    if m:
        return m.group(1)
    # Fallback: last non-empty path segment
    segments = [s for s in href.rstrip("/").split("/") if s]
    if segments:
        candidate = segments[-1].split("?")[0]
        if re.match(r"^[A-Za-z0-9_-]{3,}$", candidate):
            return candidate
    return None


def _extract_title(item) -> str | None:
    img = item.select_one("img[alt]")
    if img:
        alt = (img.get("alt") or "").strip()
        if len(alt) >= 3:
            return alt[:480]
    for sel in ("h2", "h3", "[class*='title']", "[class*='name']", "p"):
        el = item.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if len(txt) >= 3 and "¥" not in txt:
                return txt[:480]
    return None


def _extract_price(item):
    for el in item.select("[class*='price'], span, div, p"):
        txt = el.get_text(strip=True)
        if "¥" in txt or "円" in txt:
            cleaned = _JPY_STRIP_RE.sub("", txt)
            val = parse_decimal(cleaned)
            if val is not None:
                return val
    return None


def _extract_image(item) -> str | None:
    for img in item.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if src and not src.startswith("data:"):
            return src if src.startswith("http") else "https:" + src
    return None


def _extract_condition(item) -> str | None:
    for el in item.select("[class*='condition'], [class*='status'], [class*='grade'], [class*='rank']"):
        txt = el.get_text(strip=True)
        if txt:
            return txt
    return None


def _has_next(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one(f"a[href*='page={current_page + 1}']"):
        return True
    for el in soup.select("a, button"):
        label = (el.get("aria-label") or el.get_text(strip=True) or "").strip()
        if label in ("次へ", "次のページ", "Next", ">", "›", "»"):
            return True
    return False
