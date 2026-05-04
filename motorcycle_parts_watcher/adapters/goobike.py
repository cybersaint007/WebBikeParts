from __future__ import annotations

import logging

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


logger = logging.getLogger(__name__)


class GoobikeAdapter:
    """Adapter for goobike.com/parts (used parts from dealer inventories).

    BLOCKED — pure SPA: `www.goobike.com/parts/?word=...` returns a ~4kB
    HTML shell with no inline product data. The product list is fetched
    client-side from a JSON endpoint that's gated by an anti-bot token in
    the cookie jar.

    To enable: Playwright headless browser pointing at the search URL,
    then read the rendered DOM. Goobike updates inventory daily so a
    nightly crawl is sufficient.
    """

    name = "goobike"
    preferred_query_lang: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.goobike_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        logger.info("goobike: not implemented — pure SPA, requires Playwright.")
        return []
