from __future__ import annotations

import logging

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


logger = logging.getLogger(__name__)


class RakutenAdapter:
    """Adapter for search.rakuten.co.jp (Rakuten Ichiba mall).

    BLOCKED — Akamai bot challenge: every search URL returns a 43-byte
    "Reference #..." page from `server: AkamaiNetStorage`. This is the
    standard Akamai Bot Manager fingerprint check; it cannot be bypassed
    with header tweaks or session warmup.

    Real path forward — the official Rakuten Web Service:
      1. Register at https://webservice.rakuten.co.jp/ for a free Application ID
      2. Set RAKUTEN_APP_ID in .env
      3. Call `IchibaItem/Search/20220601`:
            GET https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601
              ?applicationId=<ID>&keyword=<q>&hits=30&format=json
         Returns Items[*].Item with itemName, itemPrice (JPY), itemUrl,
         mediumImageUrls, etc. — directly mappable to NormalizedListing.

    Replace this file with a real implementation once the App ID is provisioned.
    """

    name = "rakuten"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.rakuten_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        if not self.settings.rakuten_app_id:
            logger.info(
                "rakuten: not implemented — search.rakuten.co.jp is Akamai-blocked. "
                "Set RAKUTEN_APP_ID and switch to the IchibaItem/Search API."
            )
        return []
