from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryHit:
    category: str
    subcategory: str | None = None


# Keyword → (top-level category, optional subcategory). First match wins.
# Slugs match watcher.categories.slug (populated by services/catalog_sync.py).
_RULES: tuple[tuple[tuple[str, ...], CategoryHit], ...] = (
    # Modification subcategories
    (("muffler", "exhaust", "header", "mid pipe", "slip-on", "slip on"),
     CategoryHit("modification", "modification-exhaust")),
    (("piston", "crank", "cylinder", "camshaft", "engine head", "valve", "gasket"),
     CategoryHit("modification", "modification-engine")),
    (("caliper", "brake disc", "brake rotor", "rotor", "master cylinder", "brake line", "brake pad"),
     CategoryHit("modification", "modification-brakes")),
    (("fork", "shock", "suspension", "swingarm", "steering damper", "triple tree", "stem"),
     CategoryHit("modification", "modification-steering")),
    (("ecu", "cdi", "stator", "rectifier", "coil", "harness", "starter motor", "ignition"),
     CategoryHit("modification", "modification-electrical")),
    (("frame", "subframe", "chassis", "engine mount", "rearset"),
     CategoryHit("modification", "modification-chassis")),
    (("sprocket", "chain", "transmission", "clutch lever", "clutch kit", "shifter"),
     CategoryHit("modification", "modification-transmission")),
    (("fairing", "cowl", "seat cowl", "tank cover", "windshield", "fender", "tail section", "tank pad"),
     CategoryHit("modification", "modification-body")),

    # Maintenance
    (("oil filter", "engine oil", "fork oil", "brake fluid"),
     CategoryHit("maintenance", "maintenance-oils")),
    (("tire", "tyre"),
     CategoryHit("maintenance", "maintenance-tires")),
    (("battery",),
     CategoryHit("maintenance", "maintenance-batteries")),
    (("air filter", "spark plug", "service kit"),
     CategoryHit("maintenance", "maintenance-repair")),

    # Gear
    (("helmet",),
     CategoryHit("gear", "gear-helmets")),
    (("jacket", "glove", "riding suit", "leathers"),
     CategoryHit("gear", "gear-apparel")),
    (("boot", "boots"),
     CategoryHit("gear", "gear-boots")),

    # Tools
    (("torque wrench", "socket set", "allen key"),
     CategoryHit("tools", "tools-hand")),
    (("impact driver", "drill",),
     CategoryHit("tools", "tools-power")),
    (("oem", "genuine part", "original equipment"),
     CategoryHit("oem", None)),
)


def classify(title: str, description: str | None = None) -> CategoryHit:
    text = " ".join([title or "", description or ""]).lower()
    for keywords, hit in _RULES:
        if any(kw in text for kw in keywords):
            return hit
    return CategoryHit("unknown", None)


def categorize_listing(title: str, description: str | None) -> str:
    """Backwards-compatible helper: returns top-level category slug only."""
    return classify(title, description).category
