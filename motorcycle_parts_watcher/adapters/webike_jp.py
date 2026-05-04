from __future__ import annotations

import logging

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


logger = logging.getLogger(__name__)


class WebikeJpAdapter:
    """Adapter for japan.webike.net (Japanese sister of webike.tw).

    BLOCKED — geo-redirect: from non-Japan IPs both `japan.webike.net` and
    `www.webike.net` 200-redirect to `webike.tw` (already covered by the
    existing WebikeAdapter). To enable real Japanese inventory, route
    requests through a Japanese egress (residential proxy or VPN) and
    re-implement using the same `/md/{ID}` schema.org microdata pattern
    that WebikeAdapter uses.
    """

    name = "webike_jp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.webike_jp_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        logger.info(
            "webike_jp: not implemented — japan.webike.net geo-redirects to webike.tw "
            "from this region. Use a JP egress and port WebikeAdapter."
        )
        return []
