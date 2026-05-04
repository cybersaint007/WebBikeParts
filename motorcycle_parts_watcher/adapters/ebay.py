from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, parse_decimal, with_retries


logger = logging.getLogger(__name__)


class EbayAdapter:
    """eBay Browse API adapter — fans out across one or more marketplaces.

    Reads `EBAY_MARKETPLACE_IDS` (comma-separated, e.g. `EBAY_US,EBAY_GB,EBAY_DE`).
    Falls back to the legacy single-value `EBAY_MARKETPLACE_ID` if the list is empty.
    A single OAuth token is reused across all marketplace calls. Item IDs are
    globally unique, so cross-marketplace duplicates collapse on the next layer's
    `(source_name, source_item_id)` UNIQUE; here we just dedupe within the batch.
    """

    name = "ebay"
    preferred_query_lang: str | None = "en"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.ebay_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    def _marketplaces(self) -> list[str]:
        raw = (self.settings.ebay_marketplace_ids or self.settings.ebay_marketplace_id or "EBAY_US")
        return [m.strip() for m in raw.split(",") if m.strip()]

    async def _oauth_token(self) -> str:
        if not self.settings.ebay_client_id or not self.settings.ebay_client_secret:
            return ""
        auth_raw = f"{self.settings.ebay_client_id}:{self.settings.ebay_client_secret}".encode("utf-8")
        encoded_auth = base64.b64encode(auth_raw).decode("ascii")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
        async with build_async_client(self.settings) as client:
            await self._limiter.wait()
            response = await with_retries(
                lambda: client.post("https://api.ebay.com/identity/v1/oauth2/token", headers=headers, data=data),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
            return response.json().get("access_token", "")

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        token = await self._oauth_token()
        if not token:
            return []

        base = f"{bike.make} {bike.model} {bike.display_year}".strip()
        search_query = f"{base} {query}".strip() if query else f"{base} parts"
        marketplaces = self._marketplaces()

        tasks = [self._fetch_marketplace(token, search_query, mp) for mp in marketplaces]
        batches = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[NormalizedListing] = []
        seen: set[str] = set()
        for mp, batch in zip(marketplaces, batches, strict=True):
            if isinstance(batch, Exception):
                logger.warning("ebay marketplace %s failed for %s: %s", mp, bike.catalog_key, batch)
                continue
            for item in batch:
                item_id = item.get("itemId")
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                results.append(self._normalize_item(item, bike.catalog_key, mp))
        return results

    async def _fetch_marketplace(self, token: str, search_query: str, marketplace: str) -> list[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
        }
        params = {"q": search_query, "limit": "50"}
        async with build_async_client(self.settings) as client:
            await self._limiter.wait()
            response = await with_retries(
                lambda: client.get(
                    "https://api.ebay.com/buy/browse/v1/item_summary/search",
                    headers=headers,
                    params=params,
                ),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
        return response.json().get("itemSummaries", []) or []

    def _normalize_item(self, item: dict[str, Any], bike_key: str, marketplace: str) -> NormalizedListing:
        price_block = item.get("price", {}) or {}
        shipping_block = item.get("shippingOptions", [{}])[0] if item.get("shippingOptions") else {}
        shipping_cost = shipping_block.get("shippingCost", {}) if isinstance(shipping_block, dict) else {}
        seller = item.get("seller", {}) or {}

        price_value = parse_decimal(price_block.get("value"))
        shipping_value = parse_decimal(shipping_cost.get("value"))
        seller_location = seller.get("registrationAddress", {}) if isinstance(seller.get("registrationAddress"), dict) else {}

        # Tag the marketplace into raw_json so the UI can show country origin
        # and so a future query can group by source country.
        tagged = {**item, "_marketplace_id": marketplace}

        return NormalizedListing(
            source_name=self.name,
            source_item_id=item.get("itemId"),
            bike_key=bike_key,
            title=item.get("title", "").strip() or "Untitled",
            description=item.get("shortDescription"),
            url=item.get("itemWebUrl") or item.get("itemAffiliateWebUrl") or "",
            image_url=(item.get("image") or {}).get("imageUrl"),
            price_amount=price_value,
            price_currency=price_block.get("currency"),
            shipping_amount=shipping_value,
            seller_name=seller.get("username"),
            seller_country=seller_location.get("country"),
            condition=item.get("condition"),
            listing_status="active",
            raw_json=tagged,
        )
