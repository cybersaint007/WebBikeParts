from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, parse_decimal, with_retries


logger = logging.getLogger(__name__)

BUYEE_BASE = "https://buyee.jp"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class BuyeeAdapter:
    """Scrapes buyee.jp — a JP proxy-buying service that surfaces Yahoo Auctions JP
    inventory in an English-rendered DOM with international shipping built in.

    The official Yahoo Auctions Web API was retired in 2018, and direct scraping of
    auctions.yahoo.co.jp is the other option (`yahoo_auctions` adapter). Buyee is
    complementary: same auction inventory, different DOM, easier from non-JP IPs,
    and the price displayed is what the overseas buyer would actually pay.

    Each search hit is `<li class="itemCard">`:
      - `a[href*="/item/jdirectitems/auction/{ID}"]` — anchor to the listing
      - `.itemCard__itemName a` — title text
      - `.g-priceDetails__item .g-price` — price ("1,200 YEN"); the corresponding
        `.g-title` distinguishes "Current Price" / "Buyout Price" / "Price"
      - `img.g-thumbnail__image[data-src]` — lazy-loaded image
      - `.watchButton[data-auction-id]` — auction id (also derivable from URL)

    Item IDs are the Yahoo Auctions IDs (e.g. `v1228666690`) but we keep
    source_name="buyee" so rows don't collide with the `yahoo_auctions` adapter
    if both are ever live at once.
    """

    name = "buyee"
    preferred_query_lang: str | None = "ja"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.buyee_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        terms = self._build_terms(bike, query)
        if not terms:
            return []

        try:
            html = await self._fetch_html(self._search_url(terms))
        except Exception as exc:
            logger.warning("buyee fetch failed for %s (%r): %s", bike.catalog_key, terms, exc)
            return []

        return self._parse_search_page(html, bike, terms)

    # --- HTTP -------------------------------------------------------------

    def _search_url(self, terms: str) -> str:
        # /item/search/query/{q} hits the Yahoo Auctions side of Buyee.
        # lang=en renders English chrome; titles still come through in JP.
        return f"{BUYEE_BASE}/item/search/query/{quote(terms)}?lang=en"

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en;q=0.9,ja;q=0.8",
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
        if query and query.strip():
            base = f"{bike.make} {bike.model}".strip()
            return f"{base} {query.strip()}".strip()
        terms = bike.search_terms
        return terms[0].strip() if terms else ""

    def _parse_search_page(self, html: str, bike: BikeRef, terms: str) -> list[NormalizedListing]:
        soup = BeautifulSoup(html, "lxml")
        results: list[NormalizedListing] = []
        seen: set[str] = set()

        for li in soup.select("li.itemCard"):
            anchor = li.select_one("a[href*='/item/jdirectitems/']")
            if anchor is None:
                continue
            href = anchor.get("href", "")
            absolute_url = urljoin(BUYEE_BASE, href.split("?", 1)[0])
            item_id = self._extract_id(absolute_url) or self._watch_button_id(li)
            if not item_id or item_id in seen:
                continue

            title = self._best_title(li)
            if not title:
                continue

            price_amount, price_label = self._extract_price(li)
            currency = "JPY" if price_amount is not None else None
            image_url = self._best_image(li)
            bid_count = self._extract_bid_count(li)
            is_store = li.select_one(".auctionSearchResult__statusList") is not None and \
                "STORE" in li.select_one(".auctionSearchResult__statusList").get_text(" ", strip=True).upper()

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
                        "price_label": price_label,
                        "bid_count": bid_count,
                        "is_store": is_store,
                    },
                )
            )

        return results

    @staticmethod
    def _extract_id(url: str) -> str | None:
        m = re.search(r"/item/jdirectitems/[^/]+/([A-Za-z0-9]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _watch_button_id(li) -> str | None:
        btn = li.select_one(".watchButton[data-auction-id]")
        if btn is None:
            return None
        v = btn.get("data-auction-id")
        return v.strip() if v else None

    @staticmethod
    def _best_title(li) -> str | None:
        for sel in (".itemCard__itemName a", ".itemCard__itemName", "img.g-thumbnail__image"):
            el = li.select_one(sel)
            if el is None:
                continue
            txt = el.get("alt") if el.name == "img" else el.get_text(" ", strip=True)
            if txt and len(txt.strip()) >= 3:
                return txt.strip()[:480]
        return None

    @staticmethod
    def _best_image(li) -> str | None:
        img = li.select_one("img.g-thumbnail__image") or li.select_one("img")
        if img is None:
            return None
        for attr in ("data-src", "src", "data-original"):
            v = img.get(attr)
            if v and not v.startswith("data:") and "spacer.gif" not in v:
                if v.startswith("//"):
                    v = "https:" + v
                return v
        return None

    @staticmethod
    def _extract_price(li) -> tuple:
        # Prefer "Current Price" (auction) > "Buyout Price" (即決) > "Price" (store fixed).
        # Each .g-priceDetails__item pairs a .g-title label with a .g-price value.
        order = ("Current Price", "Buyout Price", "Price")
        rows = []
        for item in li.select(".g-priceDetails__item"):
            label_el = item.select_one(".g-title")
            price_el = item.select_one(".g-price")
            if price_el is None:
                continue
            label = label_el.get_text(" ", strip=True) if label_el else ""
            txt = price_el.get_text(" ", strip=True)
            rows.append((label, txt))
        for wanted in order:
            for label, txt in rows:
                if label == wanted:
                    return _parse_yen(txt), label
        if rows:
            label, txt = rows[0]
            return _parse_yen(txt), label
        return None, None

    @staticmethod
    def _extract_bid_count(li) -> int | None:
        for item in li.select(".itemCard__infoItem"):
            label_el = item.select_one(".g-title")
            if label_el is None:
                continue
            if "Bid" not in label_el.get_text(" ", strip=True):
                continue
            value_el = item.select_one(".g-text")
            if value_el is None:
                continue
            m = re.search(r"\d+", value_el.get_text(" ", strip=True))
            return int(m.group(0)) if m else None
        return None


_YEN_RE = re.compile(r"([\d,]+)")


def _parse_yen(text: str | None):
    if not text:
        return None
    m = _YEN_RE.search(text)
    if not m:
        return None
    return parse_decimal(m.group(1).replace(",", ""))
