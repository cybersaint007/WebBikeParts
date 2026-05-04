from __future__ import annotations

import logging

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.schemas import NormalizedListing


logger = logging.getLogger(__name__)


class CroooberAdapter:
    """Adapter for croooober.com (Up-Garage's used JDM parts e-commerce).

    BLOCKED — domain is dead: every URL on `www.croooober.com` 301-redirects
    to `ec.upgarage.com` which 404s for everything. The Up-Garage corporate
    rebrand appears to have left no working public catalog at either domain.
    The retail chain still exists (`www.upgarage.com` resolves to a small SPA
    landing page with no product data).

    Re-enable when a working public URL is identified, or implement against
    the in-store Mercari Shops account if Up-Garage runs one.
    """

    name = "croooober"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.croooober_enabled

    async def fetch(self, bike: BikeRef, query: str | None = None) -> list[NormalizedListing]:
        logger.info("croooober: not implemented — public catalog URL no longer exists.")
        return []
