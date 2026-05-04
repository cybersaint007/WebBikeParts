from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class NormalizedListing(BaseModel):
    source_name: str
    source_item_id: str | None = None
    bike_key: str
    title: str
    description: str | None = None
    url: str
    image_url: str | None = None
    price_amount: Decimal | None = None
    price_currency: str | None = None
    shipping_amount: Decimal | None = None
    seller_name: str | None = None
    seller_country: str | None = None
    condition: str | None = None
    category: str = "unknown"
    subcategory: str | None = None
    part_number: str | None = None
    fitment_text: str | None = None
    listing_status: str = "active"
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_json: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""

