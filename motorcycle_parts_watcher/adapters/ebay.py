from __future__ import annotations

import base64
from typing import Any

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, parse_decimal, with_retries


class EbayAdapter:
    name = "ebay"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.ebay_enabled
        self._limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

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

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.settings.ebay_marketplace_id,
        }
        params = {"q": search_query, "limit": "50"}

        async with build_async_client(self.settings) as client:
            await self._limiter.wait()
            response = await with_retries(
                lambda: client.get("https://api.ebay.com/buy/browse/v1/item_summary/search", headers=headers, params=params),
                retries=self.settings.http_retries,
                backoff_seconds=self.settings.http_retry_backoff_seconds,
            )
        payload = response.json()
        items = payload.get("itemSummaries", [])
        return [self._normalize_item(item, bike.catalog_key) for item in items]

    def _normalize_item(self, item: dict[str, Any], bike_key: str) -> NormalizedListing:
        price_block = item.get("price", {}) or {}
        shipping_block = item.get("shippingOptions", [{}])[0] if item.get("shippingOptions") else {}
        shipping_cost = shipping_block.get("shippingCost", {}) if isinstance(shipping_block, dict) else {}
        seller = item.get("seller", {}) or {}

        price_value = parse_decimal(price_block.get("value"))
        shipping_value = parse_decimal(shipping_cost.get("value"))
        seller_location = seller.get("registrationAddress", {}) if isinstance(seller.get("registrationAddress"), dict) else {}

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
            raw_json=item,
        )
