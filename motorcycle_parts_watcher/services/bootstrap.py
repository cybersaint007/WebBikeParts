from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.models import Source


def seed_sources(session: Session, settings: Settings) -> None:
    desired = {
        "ebay":            ("api",    "https://api.ebay.com",               settings.ebay_enabled),
        "yahoo_auctions":  ("api",    "https://auctions.yahoo.co.jp",       settings.yahoo_auctions_enabled),
        "buyee":           ("web",    "https://buyee.jp",                   settings.buyee_enabled),
        "webike":          ("web",    "https://www.webike.tw",              settings.webike_enabled),
        "webike_search":   ("web",    "https://www.webike.tw",              settings.webike_search_enabled),
        "webike_cat":      ("web",    "https://www.webike.tw",              settings.webike_cat_enabled),
        "webike_jp":       ("web",    "https://www.webike.jp",              settings.webike_jp_enabled),
        "croooober":       ("web",    "https://croooober.com",              settings.croooober_enabled),
        "mercari":         ("web",    "https://jp.mercari.com",             settings.mercari_enabled),
        "rakuten":         ("api",    "https://app.rakuten.co.jp",          settings.rakuten_enabled),
        "monotaro":        ("web",    "https://www.monotaro.com",           settings.monotaro_enabled),
        "goobike":         ("web",    "https://www.goobike.com",            settings.goobike_enabled),
        "old_bike_barn":   ("web",    "https://oldbikebarn.com",            settings.old_bike_barn_enabled),
        "manual_search":   ("manual", "local://manual",                     settings.manual_search_enabled),
    }
    existing_map = {src.name: src for src in session.scalars(select(Source)).all()}
    for name, (source_type, base_url, enabled) in desired.items():
        source = existing_map.get(name)
        if source is None:
            session.add(Source(name=name, type=source_type, base_url=base_url, enabled=enabled))
            continue
        source.type = source_type
        source.base_url = base_url
        source.enabled = enabled
