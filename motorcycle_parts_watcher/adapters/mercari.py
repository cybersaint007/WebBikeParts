from __future__ import annotations

import logging

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


logger = logging.getLogger(__name__)


class MercariAdapter:
    """Adapter for jp.mercari.com (peer-to-peer used marketplace).

    BLOCKED — pure SPA: jp.mercari.com is a React app served from a static
    HTML shell with no SSR data and no JSON-LD. The product list is fetched
    client-side from `api.mercari.jp/search_index/search`, which requires a
    DPoP-signed JWT (regenerated per-request from a per-device keypair).

    To enable:
      - Easiest: Playwright/Puppeteer headless browser pointing at
        `https://jp.mercari.com/search?keyword=...`, then read the rendered
        DOM. ~3-5s per query.
      - Hardest but cheapest: implement Mercari's DPoP auth flow against
        api.mercari.jp/v2/entities:search. Reverse-engineered docs exist on
        GitHub but the scheme rotates.
    """

    name = "mercari"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.mercari_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        logger.info(
            "mercari: not implemented — pure SPA, requires Playwright or DPoP-signed API."
        )
        return []
