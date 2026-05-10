"""Unit tests for the Old Bike Barn adapter.

These cover the pieces that don't need network or DB:
  * `parse_collection_title` — title shape coverage.
  * `_CollectionIndex.handles_for_bike` — case-insensitive lookup with the
    "first model token" fallback (so a webike-catalog `BikeRef` like
    `make=SUZUKI, model="GSX1100S KATANA"` still finds the OBB collection
    keyed on `GSX1100S`).
  * `OldBikeBarnAdapter._normalize` — Shopify product → NormalizedListing.
"""
from __future__ import annotations

import time

import pytest

from motorcycle_parts_watcher.adapters.old_bike_barn import (
    OldBikeBarnAdapter,
    _CollectionIndex,
    parse_collection_title,
)
from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings


def _settings() -> Settings:
    # Bypass dotenv loading; the adapter only uses http_* and old_bike_barn_enabled.
    return Settings.model_validate(
        {
            "DATABASE_URL": "postgresql+psycopg://x:x@x/x",
            "OLD_BIKE_BARN_ENABLED": "true",
        }
    )


# ---------- parse_collection_title ----------------------------------------


@pytest.mark.parametrize(
    "title,expected",
    [
        # Em-dash year range
        (
            "Suzuki GS1100 Parts (1980–1983) – OEM & Aftermarket Motorcycle Parts",
            [("Suzuki", "GS1100")],
        ),
        # ASCII hyphen year range
        (
            "Honda CB750 Parts (1969-1978) – OEM Parts",
            [("Honda", "CB750")],
        ),
        # `&` join — two model entries
        (
            "Honda CB350 & CL350 Parts (1968–1973) – OEM & Aftermarket Motorcycle Parts",
            [("Honda", "CB350"), ("Honda", "CL350")],
        ),
        # Year-in-parens BEFORE the word "Parts"
        (
            "Honda CB1000C (1983) Parts – Vintage Motorcycle Restoration & Custom Parts",
            [("Honda", "CB1000C")],
        ),
        # Single year AFTER "Parts"
        (
            "Honda CB1100F Parts (1983) – OEM & Aftermarket Motorcycle Parts",
            [("Honda", "CB1100F")],
        ),
        # Multi-word model
        (
            "Honda CMX250 Rebel 250 Parts (1985-2016)",
            [("Honda", "CMX250 Rebel 250")],
        ),
        # No year range, pipe in trailing text
        (
            "Honda CBR600 Parts | CBR600F Hurricane, F2, F3, F4, F4i & CBR600RR",
            [("Honda", "CBR600")],
        ),
        # Mixed case make
        (
            "kawasaki KZ750 Parts (1976-1983)",
            [("Kawasaki", "KZ750")],
        ),
    ],
)
def test_parse_collection_title_recognised_shapes(title, expected):
    assert parse_collection_title(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        # Category-style with colon — would otherwise false-match on "CB750 Parts"
        "Honda CB750: Electrical Parts",
        # Generic part-category collection — no recognised make
        "Oil Pumps – 2135",
        # Empty
        "",
        # Make alone (no Parts keyword)
        "Suzuki",
        # Make + model but no "Parts" keyword
        "Suzuki GS1100 1980-1983",
    ],
)
def test_parse_collection_title_rejects_non_bike_shapes(title):
    assert parse_collection_title(title) == []


# ---------- _CollectionIndex.handles_for_bike -----------------------------


def _build_index(collections):
    by_key: dict[tuple[str, str], list[str]] = {}
    for handle, title in collections:
        for make, model in parse_collection_title(title):
            by_key.setdefault((make.lower(), model.lower()), []).append(handle)
            head = model.split()[0] if model.split() else ""
            if head and head.lower() != model.lower():
                by_key.setdefault((make.lower(), head.lower()), []).append(handle)
    return _CollectionIndex(by_key=by_key, built_at=time.time(), collections_count=len(collections))


def test_handles_for_bike_matches_uppercase_make_from_catalog():
    idx = _build_index(
        [
            (
                "suzuki-gs1100-oem-aftermarket-parts",
                "Suzuki GS1100 Parts (1980–1983) – OEM & ...",
            ),
        ]
    )
    bike = BikeRef(
        catalog_key="suzuki-gs1100-1981",
        make="SUZUKI",  # webike scraper writes makes uppercased
        model="GS1100",
        year_start=1981,
        year_end=1981,
    )
    assert idx.handles_for_bike(bike) == ["suzuki-gs1100-oem-aftermarket-parts"]


def test_handles_for_bike_falls_back_to_first_model_token():
    """webike catalog model "GSX1100S KATANA" should still find OBB's GSX1100S handle."""
    idx = _build_index(
        [
            (
                "suzuki-gsx1100s-oem-parts",
                "Suzuki GSX1100S Parts (1981–1986) – OEM & Aftermarket Motorcycle Parts",
            ),
        ]
    )
    bike = BikeRef(
        catalog_key="suzuki-gsx1100s-katana-1982",
        make="SUZUKI",
        model="GSX1100S KATANA",  # multi-token model from webike
        year_start=1982,
        year_end=1982,
    )
    assert idx.handles_for_bike(bike) == ["suzuki-gsx1100s-oem-parts"]


def test_handles_for_bike_empty_when_unknown():
    idx = _build_index([])
    bike = BikeRef(
        catalog_key="x",
        make="Suzuki",
        model="UNKNOWNXYZ",
        year_start=1980,
        year_end=1980,
    )
    assert idx.handles_for_bike(bike) == []


def test_handles_for_bike_returns_both_handles_for_amp_join_collection():
    """A "CB350 & CL350" collection should be findable by either model."""
    idx = _build_index(
        [
            (
                "honda-cb350-cl350-oem-aftermarket-parts",
                "Honda CB350 & CL350 Parts (1968–1973) – OEM & ...",
            ),
        ]
    )
    bike_cb = BikeRef(
        catalog_key="honda-cb350-1970", make="Honda", model="CB350",
        year_start=1970, year_end=1970,
    )
    bike_cl = BikeRef(
        catalog_key="honda-cl350-1970", make="Honda", model="CL350",
        year_start=1970, year_end=1970,
    )
    assert idx.handles_for_bike(bike_cb) == ["honda-cb350-cl350-oem-aftermarket-parts"]
    assert idx.handles_for_bike(bike_cl) == ["honda-cb350-cl350-oem-aftermarket-parts"]


# ---------- OldBikeBarnAdapter._normalize ---------------------------------


def test_normalize_real_shopify_product_shape():
    """Mirror the actual /collections/.../products.json response observed for GS1100."""
    adapter = OldBikeBarnAdapter(_settings())
    bike = BikeRef(
        catalog_key="suzuki-gs1100-1982", make="Suzuki", model="GS1100",
        year_start=1982, year_end=1983,
    )
    prod = {
        "id": 9034867277979,
        "title": "Suzuki 82-83 GS1100E/ES/S Engine Gasket Set",
        "handle": "suzuki-82-83-gs1100e-es-s-engine-gasket-set",
        "body_html": "<p>Complete top-end gasket kit.</p>",
        "vendor": "OBB",
        "product_type": "Engine",
        "tags": [
            "Engine",
            "Engine Gasket Sets",
            "Model Specific: GS1100",
        ],
        "variants": [
            {
                "sku": "18-0175",
                "price": "183.69",
                "available": True,
                "compare_at_price": None,
            }
        ],
        "images": [
            {"src": "https://cdn.shopify.com/s/files/1/0215/9889/6228/files/gs1100-gasket-set.jpg"}
        ],
    }

    listing = adapter._normalize(prod, bike, "suzuki-gs1100-oem-aftermarket-parts", query=None)
    assert listing is not None
    assert listing.source_name == "old_bike_barn"
    assert listing.source_item_id == "9034867277979"
    assert listing.bike_key == "suzuki-gs1100-1982"
    assert listing.title == "Suzuki 82-83 GS1100E/ES/S Engine Gasket Set"
    assert listing.url == (
        "https://oldbikebarn.com/products/suzuki-82-83-gs1100e-es-s-engine-gasket-set"
    )
    assert listing.image_url.endswith("gs1100-gasket-set.jpg")
    assert str(listing.price_amount) == "183.69"
    assert listing.price_currency == "USD"
    assert listing.part_number == "18-0175"
    assert listing.category == "Engine"
    assert listing.listing_status == "active"
    assert "Model Specific: GS1100" in (listing.fitment_text or "")


def test_normalize_marks_unavailable_as_out_of_stock():
    adapter = OldBikeBarnAdapter(_settings())
    bike = BikeRef(catalog_key="x", make="Suzuki", model="GS1100",
                   year_start=1982, year_end=1982)
    prod = {
        "id": 1,
        "title": "Test Part",
        "handle": "test-part",
        "variants": [{"sku": "X-1", "price": "10.00", "available": False}],
        "images": [],
        "tags": [],
        "product_type": "Misc",
    }
    listing = adapter._normalize(prod, bike, "suzuki-gs1100-oem-aftermarket-parts", query=None)
    assert listing is not None
    assert listing.listing_status == "out_of_stock"


def test_normalize_skips_product_without_handle_or_title():
    adapter = OldBikeBarnAdapter(_settings())
    bike = BikeRef(catalog_key="x", make="Suzuki", model="GS1100",
                   year_start=1982, year_end=1982)
    assert adapter._normalize({"id": 1, "title": ""}, bike, "h", None) is None
    assert adapter._normalize({"id": 1, "handle": ""}, bike, "h", None) is None
