"""Mercari JP — keyword search via headless Chromium (Playwright).

jp.mercari.com is a pure React SPA. We drive its /search?keyword=...
endpoint with Playwright, wait for item cards to render, then parse the
resulting DOM with BeautifulSoup. Results are JP-locale listings priced
in JPY.

preferred_query_lang = "ja" so the producer translates queries to
Japanese before enqueuing.
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

MERCARI_BASE = "https://jp.mercari.com"
MAX_PAGES = 5
_BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_ITEM_ID_RE = re.compile(r"/item/(m\d+)")
_JPY_STRIP_RE = re.compile(r"[¥円,\s]")


class MercariAdapter:
    """Mercari JP search via Playwright headless Chromium."""

    name = "mercari"
    preferred_query_lang: str | None = "ja"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.mercari_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("mercari: playwright not installed; run `playwright install chromium --with-deps`")
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
                        url = f"{MERCARI_BASE}/search?keyword={quote(search_query)}&status=on_sale"
                        if page_num > 1:
                            url += f"&page={page_num}"

                        page = await context.new_page()
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                            try:
                                await page.wait_for_selector(
                                    "li[data-testid='item-cell']", timeout=15_000
                                )
                            except Exception:
                                logger.debug(
                                    "mercari: no items on page %d for %s", page_num, bike.catalog_key
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
            logger.warning("mercari: fetch failed for %s: %s", bike.catalog_key, exc)

        logger.info("mercari: %d listings for %s", len(results), bike.catalog_key)
        return results


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_items(
    html: str, bike: BikeRef, search_query: str, seen_ids: set[str]
) -> list[NormalizedListing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[NormalizedListing] = []

    for cell in soup.select("li[data-testid='item-cell']"):
        anchor = cell.select_one("a[href*='/item/m']")
        if not anchor:
            continue
        href = anchor.get("href", "")
        m = _ITEM_ID_RE.search(href)
        if not m:
            continue
        item_id = m.group(1)
        if item_id in seen_ids:
            continue

        title = _extract_title(cell)
        if not title:
            continue

        url = href if href.startswith("http") else MERCARI_BASE + href
        seen_ids.add(item_id)
        results.append(
            NormalizedListing(
                source_name="mercari",
                source_item_id=item_id,
                bike_key=bike.catalog_key,
                title=title,
                url=url,
                image_url=_extract_image(cell),
                price_amount=_extract_price(cell),
                price_currency="JPY",
                condition=_extract_condition(cell),
                listing_status="active",
                raw_json={"search_query": search_query},
            )
        )

    return results


def _extract_title(cell) -> str | None:
    # Mercari renders item name as the img alt attribute in search results
    img = cell.select_one("img[alt]")
    if img:
        alt = (img.get("alt") or "").strip()
        if len(alt) >= 3:
            return alt[:480]
    # Fall back to first text block that isn't a price
    for el in cell.select("p, span"):
        txt = el.get_text(strip=True)
        if len(txt) >= 3 and "¥" not in txt and "円" not in txt:
            return txt[:480]
    return None


def _extract_price(cell):
    for el in cell.select("span, div, p"):
        txt = el.get_text(strip=True)
        if "¥" in txt or "円" in txt:
            cleaned = _JPY_STRIP_RE.sub("", txt)
            val = parse_decimal(cleaned)
            if val is not None:
                return val
    return None


def _extract_image(cell) -> str | None:
    img = cell.select_one("img[src]")
    if img:
        src = img.get("src", "")
        if src and not src.startswith("data:"):
            return src if src.startswith("http") else "https:" + src
    return None


def _extract_condition(cell) -> str | None:
    # Mercari condition badges rendered as mer-tag or tagged spans
    for el in cell.select("mer-tag, [class*='condition'], [class*='status']"):
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
