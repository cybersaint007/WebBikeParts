from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from motorcycle_parts_watcher.schemas import NormalizedListing


def _clean_decimal(value: Decimal | None) -> str:
    return str(value) if value is not None else ""


def listing_hash_payload(listing: NormalizedListing) -> dict[str, Any]:
    return {
        "source_name": listing.source_name,
        "source_item_id": listing.source_item_id,
        "bike_key": listing.bike_key,
        "title": listing.title.strip().lower(),
        "description": (listing.description or "").strip().lower(),
        "price_amount": _clean_decimal(listing.price_amount),
        "price_currency": (listing.price_currency or "").upper(),
        "condition": (listing.condition or "").strip().lower(),
        "part_number": (listing.part_number or "").strip().lower(),
    }


def compute_content_hash(listing: NormalizedListing) -> str:
    payload = listing_hash_payload(listing)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

