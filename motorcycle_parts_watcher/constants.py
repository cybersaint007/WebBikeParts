from __future__ import annotations

from dataclasses import dataclass


PART_CATEGORIES: tuple[str, ...] = (
    "engine",
    "carb_fuel",
    "exhaust",
    "electrical",
    "suspension",
    "brakes",
    "bodywork",
    "frame_chassis",
    "wheels_tires",
    "controls",
    "maintenance",
    "unknown",
)


@dataclass(frozen=True)
class BikeSeed:
    key: str
    name: str
    make: str
    model: str
    year: int
    variant: str
    aliases: list[str]


BIKE_SEEDS: tuple[BikeSeed, ...] = (
    BikeSeed(
        key="katana1100",
        name="1990 Suzuki Katana 1100 SL",
        make="Suzuki",
        model="Katana 1100",
        year=1990,
        variant="GSX1100S / GS110X",
        aliases=["GSX1100S", "GS110X", "Katana 1100 SL"],
    ),
    BikeSeed(
        key="hayabusa2003",
        name="2003 Suzuki GSX1300R Hayabusa",
        make="Suzuki",
        model="GSX1300R Hayabusa",
        year=2003,
        variant="Gen 1",
        aliases=["GSX1300R", "Hayabusa 2003", "Busa 2003"],
    ),
)

