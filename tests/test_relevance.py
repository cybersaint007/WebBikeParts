"""Unit tests for the bike-relevance filter used by IngestService.

No DB or network dependencies — pure functions on BikeRef + NormalizedListing.
"""
from __future__ import annotations

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.relevance import (
    is_relevant_for_bike,
    relevance_tokens,
)


def _bike(make: str, model: str, year_start: int = 0, year_end: int = 0) -> BikeRef:
    return BikeRef(
        catalog_key=f"{make.lower()}-{model.lower().replace(' ', '-')}",
        make=make, model=model, year_start=year_start, year_end=year_end,
    )


def _listing(title: str, *, description: str | None = None, fitment: str | None = None) -> NormalizedListing:
    return NormalizedListing(
        source_name="test", source_item_id="x", bike_key="x",
        title=title, description=description, fitment_text=fitment,
        url="https://example.test/x",
    )


def test_tokens_split_make_and_model_and_lowercase():
    bike = _bike("SUZUKI", "GSX1100S KATANA", 1990, 1993)
    toks = relevance_tokens(bike)
    # Both raw "gsx1100s" and the numeric-stripped "gsx1100" are present.
    assert "suzuki" in toks
    assert "gsx1100s" in toks
    assert "gsx1100" in toks
    assert "katana" in toks


def test_tokens_include_japanese_aliases_for_known_makes_and_models():
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    toks = relevance_tokens(bike)
    assert "スズキ" in toks
    assert "カタナ" in toks
    assert "刀" in toks


def test_match_passes_when_title_contains_model():
    bike = _bike("SUZUKI", "GSX1100S KATANA", 1990, 1993)
    listing = _listing("Suzuki GSX1100S Katana Starter Cover - GSX1100S 82-84")
    assert is_relevant_for_bike(listing, bike) is True


def test_match_passes_on_japanese_alias_in_title():
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    listing = _listing("カタナ用 クラッチカバー 純正")
    assert is_relevant_for_bike(listing, bike) is True


def test_match_passes_when_only_make_is_present():
    # A listing tagged only with the maker (no model number) still relevant —
    # the user can refine further with the search box.
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    listing = _listing("Suzuki universal mirror set")
    assert is_relevant_for_bike(listing, bike) is True


def test_match_uses_description_when_title_misses():
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    listing = _listing(
        "Engine Side Cover OEM",
        description="Fits Suzuki GSX1100S 1990-1993",
    )
    assert is_relevant_for_bike(listing, bike) is True


def test_drops_unrelated_make_in_title():
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    # A real eBay/Mercari false positive seen in production.
    assert is_relevant_for_bike(
        _listing("2009 - 2019 TOYOTA COROLLA Timing Cover 1.8L OEM"),
        bike,
    ) is False
    assert is_relevant_for_bike(
        _listing("Engine Stator Cover See Through Honda CBR 1000 RR 2006-2007"),
        bike,
    ) is False
    assert is_relevant_for_bike(
        _listing("Moose Ignition Cover Matte Black #D70-4476MB for Yamaha YZ125/YZ125X"),
        bike,
    ) is False


def test_drops_japanese_keyword_collisions():
    # "クラッチバッグ" (clutch bag, the handbag) and "手帳カバー" (notebook
    # cover) are real Mercari noise from the 'クラッチカバー' search.
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    assert is_relevant_for_bike(_listing("【本日限定】 SHIPS クラッチバッグ"), bike) is False
    assert is_relevant_for_bike(_listing("手帳カバー 黒色"), bike) is False
    assert is_relevant_for_bike(
        _listing("MAZDA バルブキャップ エアバルブステムカバー"),
        bike,
    ) is False


def test_drops_when_text_empty():
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    listing = _listing("")
    assert is_relevant_for_bike(listing, bike) is False


def test_accepts_everything_when_bike_has_no_tokens():
    # Defensive: don't silently drop everything if BikeRef is malformed.
    bike = _bike("", "")
    listing = _listing("Random part")
    assert is_relevant_for_bike(listing, bike) is True


def test_bmw_k1200r_keeps_genuine_match():
    bike = _bike("BMW", "K1200R")
    assert is_relevant_for_bike(
        _listing("BMW K1200R Sport Carbon Fiber Tank Cover"),
        bike,
    ) is True


def test_bmw_k1200r_drops_unrelated_yamaha():
    bike = _bike("BMW", "K1200R")
    assert is_relevant_for_bike(
        _listing("Yamaha R1 frame slider kit"),
        bike,
    ) is False


def test_match_handles_separator_variants_in_model_number():
    # Sellers write GSX1100S as "GSX-1100S", "GSX 1100S", "GSX_1100S".
    # All should still match the "gsx1100s" token.
    bike = _bike("SUZUKI", "GSX1100S KATANA")
    assert is_relevant_for_bike(_listing("SCR 開路型整流器 GSX-1100S"), bike) is True
    assert is_relevant_for_bike(_listing("Carb kit GSX 1100S"), bike) is True
    assert is_relevant_for_bike(_listing("Replacement part GSX_1100S"), bike) is True


def test_match_handles_separator_variants_in_bmw_model():
    bike = _bike("BMW", "K1200R")
    assert is_relevant_for_bike(_listing("Carbon cover K-1200R Sport"), bike) is True
    assert is_relevant_for_bike(_listing("ABS pump for K 1200 R"), bike) is True
