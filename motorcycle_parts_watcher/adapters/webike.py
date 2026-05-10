from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, parse_decimal, with_retries


logger = logging.getLogger(__name__)

WEBIKE_BASE = "https://www.webike.tw"
USER_AGENT = "Mozilla/5.0 (compatible; motorcycle-parts-watcher/0.1)"
MAX_PAGES = 100  # webike model pages can reach 60+ pages for popular bikes


class WebikeAdapter:
    """Pulls product listings for a bike by scraping its /md/{MODEL_ID} page on webike.tw.

    Webike's keyword search (/search?q=...) is JS-rendered, but the per-bike model page is
    plain HTML with ~40 product cards per page. We use the catalog row's `webike_url`
    (populated by services/catalog_sync.py) as the entry point and paginate until the
    last page, so niche parts buried deep in the listing (e.g. brand-filtered sub-categories
    that appear only on later pages) are not missed.
    """

    name = "webike"
    preferred_query_lang: str | None = "zh-TW"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        if not bike.webike_url:
            logger.info("webike: bike %s has no webike_url; skipping", bike.catalog_key)
            return []

        results: list[NormalizedListing] = []
        seen_ids: set[str] = set()
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

        # The catalog stores /md/{id} URLs; /parts/md/{id} is the full paginated catalog.
        parts_url = bike.webike_url.replace("/md/", "/parts/md/", 1)

        try:
            async with build_async_client(self.settings) as client:
                await self._limiter.wait()
                response = await with_retries(
                    lambda: client.get(parts_url, headers=headers),
                    retries=self.settings.http_retries,
                    backoff_seconds=self.settings.http_retry_backoff_seconds,
                )
                final_url = str(response.url)
                if WEBIKE_BASE not in final_url:
                    raise RuntimeError(
                        f"webike.tw redirected to {final_url!r} — IP may be geo-blocked; "
                        "set WEBIKE_PROXY_URL to a residential proxy to bypass"
                    )
                response.raise_for_status()
                base_url = final_url.split("?")[0]

                for page_num in range(1, MAX_PAGES + 1):
                    page_results = self._parse_page(response.text, bike, seen_ids)
                    results.extend(page_results)
                    if not page_results or not self._has_next_page(response.text, page_num):
                        break
                    await self._limiter.wait()
                    next_url = f"{base_url}?page={page_num + 1}"
                    response = await with_retries(
                        lambda: client.get(next_url, headers=headers),
                        retries=self.settings.http_retries,
                        backoff_seconds=self.settings.http_retry_backoff_seconds,
                    )
                    response.raise_for_status()

        except Exception as exc:
            logger.warning("webike fetch failed for %s: %s", bike.catalog_key, exc)
            return results

        if query:
            q_lower = query.lower()
            results = [r for r in results if q_lower in r.title.lower()]
        return results

    def _parse_page(self, html: str, bike: BikeRef, seen_ids: set[str]) -> list[NormalizedListing]:
        """Parse one page of a webike /md/{ID} listing.

        Each priced product card uses schema.org microdata:
            <div class="item__body p-2">
              <a href="/sd/{ID}">…</a>
              <img alt="title" src="…">
              <meta itemprop="price" content="499">
              <meta itemprop="priceCurrency" content="TWD">
            </div>

        We iterate meta[itemprop=price] so we get only real product cards (skipping
        the "recently viewed" / "you may also like" duplicate anchors that have no price).
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[NormalizedListing] = []

        for price_meta in soup.select("meta[itemprop='price']"):
            container = self._find_product_container(price_meta)
            if container is None:
                continue
            anchor = container.select_one("a[href*='/sd/']")
            if anchor is None:
                continue
            absolute_url = urljoin(WEBIKE_BASE, anchor.get("href", ""))
            item_id = self._extract_id(absolute_url)
            if not item_id or item_id in seen_ids:
                continue

            title = self._best_title(container)
            if not title or len(title) < 3:
                continue

            image_url = self._best_image(container)
            price_amount = parse_decimal(price_meta.get("content"))
            currency_meta = container.select_one("meta[itemprop='priceCurrency']")
            currency = currency_meta.get("content") if currency_meta else None

            seen_ids.add(item_id)
            results.append(
                NormalizedListing(
                    source_name=self.name,
                    source_item_id=item_id,
                    bike_key=bike.catalog_key,
                    title=title,
                    description=None,
                    url=absolute_url,
                    image_url=image_url,
                    price_amount=price_amount,
                    price_currency=currency,
                    listing_status="active",
                    raw_json={"source_url": bike.webike_url},
                )
            )

        return results

    @staticmethod
    def _has_next_page(html: str, current_page: int) -> bool:
        soup = BeautifulSoup(html, "lxml")
        return bool(soup.select_one(f"a[href*='page={current_page + 1}']"))

    @staticmethod
    def _find_product_container(price_meta) -> Any:
        """Walk up from a price <meta> to the nearest container that holds the /sd/ anchor."""
        node = price_meta
        for _ in range(8):
            node = node.parent
            if node is None:
                return None
            if node.select_one("a[href*='/sd/']"):
                return node
        return None

    @staticmethod
    def _best_image(container) -> str | None:
        # Webike's product image lives in a sibling .item__header__img *outside* item__body,
        # so search the container, then walk up to find it.
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

    @staticmethod
    def _best_title(anchor) -> str:
        # Prefer img alt > a[title] > visible text. webike uses 商品名稱 in titles.
        for sel in ("img", ".product-name", ".name", "[class*='title']"):
            el = anchor.select_one(sel)
            if el is None:
                continue
            for attr in ("alt", "title"):
                v = el.get(attr) if hasattr(el, "get") else None
                if v and len(v.strip()) >= 3:
                    return v.strip()[:480]
            txt = el.get_text(strip=True)
            if txt and len(txt) >= 3:
                return txt[:480]
        if title := anchor.get("title"):
            return title.strip()[:480]
        txt = anchor.get_text(" ", strip=True)
        # Strip "詳細" / "更多" links etc.
        return txt[:480]

    @staticmethod
    def _best_price_text(anchor) -> str | None:
        for sel in (".price", "[class*='price']", "[class*='Price']"):
            el = anchor.select_one(sel)
            if el is not None:
                t = el.get_text(" ", strip=True)
                if t:
                    return t
        return None

    @staticmethod
    def _extract_id(url: str) -> str | None:
        m = re.search(r"/sd/([0-9A-Za-z_-]+)", url)
        return m.group(1) if m else None


_PRICE_RE = re.compile(r"([0-9]+(?:[,.][0-9]+)*)")


def _parse_price(text: str | None) -> tuple[Decimal | None, str | None]:
    if not text:
        return None, None
    cleaned = text.replace(",", "")
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None, None
    amount = parse_decimal(m.group(1))
    currency = "TWD" if any(sym in text for sym in ("NT$", "TWD", "$")) else None
    return amount, currency
