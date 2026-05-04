from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, parse_decimal, with_retries


logger = logging.getLogger(__name__)

YAHOO_BASE = "https://auctions.yahoo.co.jp"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class YahooAuctionsAdapter:
    """Scrapes the public Yahoo Auctions Japan search page (auctions.yahoo.co.jp/search/search).

    No API credentials required. Each result `<li class="Product">` contains:
      - anchor to /jp/auction/{ID}
      - <h3> title
      - .Product__priceValue.u-textRed → current bid price in JPY
      - sibling .Product__price with "即決" → buy-now price (optional)
      - .Product__bidWrap → bid count
      - <img> in .Product__image
    """

    name = "yahoo_auctions"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.yahoo_auctions_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        terms = self._build_terms(bike, query)
        if not terms:
            return []

        try:
            html = await self._fetch_html(self._search_url(terms))
        except Exception as exc:
            logger.warning("yahoo_auctions fetch failed for %s (%r): %s", bike.catalog_key, terms, exc)
            return []

        return self._parse_search_page(html, bike, terms)

    # --- HTTP -------------------------------------------------------------

    def _search_url(self, terms: str) -> str:
        q = quote(terms)
        # n=50 → up to 50 results per page (default 20). va= ensures phrase-style query.
        return f"{YAHOO_BASE}/search/search?p={q}&va={q}&n=50"

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en;q=0.8",
        }
        async with build_async_client(self.settings) as client:
            await self._limiter.wait()
            response = await with_retries(
                lambda: client.get(url, headers=headers),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
        return response.text

    # --- Parsing ----------------------------------------------------------

    def _build_terms(self, bike: BikeRef, query: str | None) -> str:
        # User-supplied query takes precedence (e.g. live-search "exhaust slip-on").
        if query and query.strip():
            base = f"{bike.make} {bike.model}".strip()
            return f"{base} {query.strip()}".strip()
        # Otherwise pull the first BikeRef-built search term.
        terms = bike.search_terms
        return terms[0].strip() if terms else ""

    def _parse_search_page(self, html: str, bike: BikeRef, terms: str) -> list[NormalizedListing]:
        soup = BeautifulSoup(html, "lxml")
        results: list[NormalizedListing] = []
        seen: set[str] = set()

        for li in soup.select("li.Product"):
            anchor = li.select_one("a[href*='/jp/auction/']")
            if anchor is None:
                continue
            href = anchor.get("href", "")
            absolute_url = urljoin(YAHOO_BASE, href)
            item_id = self._extract_id(absolute_url)
            if not item_id or item_id in seen:
                continue

            title = self._best_title(li)
            if not title:
                continue

            price_amount = self._extract_current_price(li)
            currency = "JPY" if price_amount is not None else None
            image_url = self._best_image(li)
            bid_count = self._extract_bid_count(li)
            has_buy_now = li.select_one(".Product__price:nth-of-type(2)") is not None

            seen.add(item_id)
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
                    raw_json={
                        "search_terms": terms,
                        "bid_count": bid_count,
                        "has_buy_now": has_buy_now,
                    },
                )
            )

        return results

    @staticmethod
    def _extract_id(url: str) -> str | None:
        # Auction IDs look like 1225854667 or v1228694564 (letter prefix denotes seller region).
        m = re.search(r"/jp/auction/([A-Za-z0-9]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _best_title(li) -> str | None:
        for sel in ("h3 a", "h3", "[class*='Title'] a", "[class*='Title']", "a[href*='/jp/auction/']"):
            el = li.select_one(sel)
            if el is None:
                continue
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) >= 3:
                return txt[:480]
        return None

    @staticmethod
    def _best_image(li) -> str | None:
        for img in li.select("img"):
            for attr in ("src", "data-src", "data-original"):
                v = img.get(attr)
                if v and not v.startswith("data:"):
                    if v.startswith("//"):
                        v = "https:" + v
                    return v
        return None

    @staticmethod
    def _extract_current_price(li) -> Any:
        # The "current" price is the first .Product__priceValue inside the first .Product__price block.
        # u-textRed is the "current bid" highlight class.
        el = li.select_one(".Product__priceValue.u-textRed") or li.select_one(".Product__priceValue")
        if el is None:
            return None
        txt = el.get_text(" ", strip=True).replace(",", "").replace("円", "")
        m = re.search(r"\d+(?:\.\d+)?", txt)
        return parse_decimal(m.group(0)) if m else None

    @staticmethod
    def _extract_bid_count(li) -> int | None:
        el = li.select_one(".Product__bidWrap")
        if el is None:
            return None
        txt = el.get_text(" ", strip=True)
        m = re.search(r"\d+", txt)
        return int(m.group(0)) if m else None
