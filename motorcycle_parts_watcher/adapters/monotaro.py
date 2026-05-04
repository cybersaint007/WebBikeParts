from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, with_retries


logger = logging.getLogger(__name__)

MONOTARO_BASE = "https://www.monotaro.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class MonotaroAdapter:
    """Scrapes monotaro.com search results.

    Monotaro is an industrial supply catalog — strong on bolts, bearings, oils,
    maintenance items by part number. Pricing is loaded via Next.js streaming RSC
    chunks rather than static HTML, so we only extract product code, title, and
    image from /g/{code}/ anchors. Prices remain null and are populated by the
    snapshot/dedup layer when listings are re-seen.
    """

    name = "monotaro"
    preferred_query_lang: str | None = "ja"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.monotaro_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        terms = self._build_terms(bike, query)
        if not terms:
            return []
        try:
            html = await self._fetch_html(self._search_url(terms))
        except Exception as exc:
            logger.warning("monotaro fetch failed for %s (%r): %s", bike.catalog_key, terms, exc)
            return []
        return self._parse_search(html, bike, terms)

    def _search_url(self, terms: str) -> str:
        return f"{MONOTARO_BASE}/s/?q={quote(terms)}"

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

    def _build_terms(self, bike: BikeRef, query: str | None) -> str:
        if query and query.strip():
            return query.strip()
        # Monotaro is parts-by-keyword; the bike name alone returns mostly noise.
        # Prefer model name only (drop year) for a slightly tighter query.
        return f"{bike.make} {bike.model}".strip()

    def _parse_search(self, html: str, bike: BikeRef, terms: str) -> list[NormalizedListing]:
        soup = BeautifulSoup(html, "lxml")
        results: list[NormalizedListing] = []
        seen: set[str] = set()
        for anchor in soup.select("a[href*='/g/']"):
            m = re.search(r"/g/(\d+)", anchor.get("href", ""))
            if not m:
                continue
            code = m.group(1)
            if code in seen:
                continue
            img = anchor.select_one("img") or anchor.find_next("img")
            title = (anchor.get("title") or "").strip()
            if not title and img is not None:
                title = (img.get("alt") or "").strip()
            if not title:
                title = anchor.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue
            image_url = None
            if img is not None:
                image_url = img.get("src") or img.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            seen.add(code)
            results.append(
                NormalizedListing(
                    source_name=self.name,
                    source_item_id=code,
                    bike_key=bike.catalog_key,
                    title=title[:480],
                    description=None,
                    url=urljoin(MONOTARO_BASE, f"/g/{code}/"),
                    image_url=image_url,
                    price_amount=None,
                    price_currency=None,
                    listing_status="active",
                    raw_json={"search_terms": terms},
                )
            )
        return results
