from __future__ import annotations

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


class YahooAuctionsAdapter:
    name = "yahoo_auctions"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.yahoo_auctions_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        # Optional source placeholder. Integrate official API credentials if enabled in your environment.
        return []

