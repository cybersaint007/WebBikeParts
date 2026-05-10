"""Post-fetch relevance filter for keyword-search adapters.

Some adapters (eBay, Mercari, Monotaro, ...) reach a source via plain keyword
search and tag every result with the bike that triggered the crawl, regardless
of what the listing actually fits. That means searches like "クラッチカバー"
return handbags ("クラッチバッグ") and Toyota Corolla timing covers under a
Suzuki Katana bike key.

This module supplies the gate the ingest layer uses to drop results whose
title/description/fitment text contains no recognisable token of the target
bike's make or model. Bike-scoped adapters (those that fetch from a per-bike
URL — `webike`, `old_bike_barn`, ...) bypass the check.
"""
from __future__ import annotations

import re

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.schemas import NormalizedListing


# Japanese aliases for makes and high-profile model names that routinely
# appear in JP listings as kana/kanji rather than Latin. Keep this short —
# model numbers (GSX1100S, K1200R, R1, ...) tend to stay in Latin even on
# Japanese sites and don't need entries here.
_JP_ALIASES: dict[str, tuple[str, ...]] = {
    "suzuki":   ("スズキ",),
    "honda":    ("ホンダ",),
    "yamaha":   ("ヤマハ",),
    "kawasaki": ("カワサキ",),
    "ducati":   ("ドゥカティ",),
    "katana":   ("カタナ", "刀"),
    "hayabusa": ("ハヤブサ", "隼"),
    "ninja":    ("ニンジャ",),
}


_TOKEN_SPLIT_RE = re.compile(r"[\s\-_/.,()]+")
# Numeric-suffix model names (GSX1100S, GSX1100, K1200R, ...) — strip the
# trailing letter to also accept the bare-number form.
_NUMERIC_SUFFIX_RE = re.compile(r"^([A-Z]+\d+)[A-Z]+$", re.IGNORECASE)
# Sellers spell model numbers many ways: GSX1100S / GSX-1100S / GSX 1100S /
# GSX_1100S. Strip all of these from the haystack before substring matching
# so one token form catches all of them.
_HAYSTACK_NOISE_RE = re.compile(r"[\s\-_/.,()]+")


def relevance_tokens(bike: BikeRef) -> list[str]:
    """Lowercase tokens that a relevant listing should contain at least one of.

    Generated from make + model: each whitespace/punctuation-separated piece
    becomes a token, model-number variants like "GSX1100S" → "gsx1100" are
    added as additional tokens, and Japanese aliases for known makes/models
    are appended so JP-locale listings still match.
    """
    raw: set[str] = set()
    for piece in (bike.make or "", bike.model or ""):
        for tok in _TOKEN_SPLIT_RE.split(piece.lower()):
            tok = tok.strip()
            if len(tok) < 2:
                continue
            raw.add(tok)
            m = _NUMERIC_SUFFIX_RE.match(tok)
            if m:
                raw.add(m.group(1).lower())

    for tok in list(raw):
        for alias in _JP_ALIASES.get(tok, ()):
            raw.add(alias.lower())

    return sorted(raw)


def is_relevant_for_bike(listing: NormalizedListing, bike: BikeRef) -> bool:
    """True if the listing's text mentions at least one bike token.

    Concatenates title + description + fitment_text, lowercases, and tests
    every token as a substring. Empty-token bikes (no make/model) accept
    everything to avoid silently dropping all results.
    """
    tokens = relevance_tokens(bike)
    if not tokens:
        return True
    haystack = " ".join(filter(None, [
        listing.title,
        listing.description,
        listing.fitment_text,
    ])).lower()
    if not haystack:
        return False
    # Match against both the raw lowercased text and a separator-stripped
    # variant so "GSX-1100S" / "GSX 1100S" / "GSX_1100S" all hit the
    # "gsx1100s" token. Japanese kana tokens (カタナ, スズキ) have no internal
    # separators so the second form doesn't help or hurt them.
    squeezed = _HAYSTACK_NOISE_RE.sub("", haystack)
    return any(tok in haystack or tok in squeezed for tok in tokens)
