from __future__ import annotations

from typing import Protocol

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.schemas import NormalizedListing


class ListingAdapter(Protocol):
    name: str
    enabled: bool
    # True for adapters that reach a source via plain keyword search and have
    # no per-bike URL of their own. The ingest layer applies a relevance check
    # to those, dropping results whose text contains no recognisable bike
    # token. False for adapters that fetch from a per-bike URL/category page,
    # where the bike fitment is implicit in the URL the adapter visited.
    is_keyword_search: bool

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        ...
