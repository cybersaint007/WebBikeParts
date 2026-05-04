from __future__ import annotations

from typing import Protocol

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.schemas import NormalizedListing


class ListingAdapter(Protocol):
    name: str
    enabled: bool

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        ...
