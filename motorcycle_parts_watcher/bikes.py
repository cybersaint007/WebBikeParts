from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BikeRef:
    """Lightweight bike descriptor passed to adapters.

    `catalog_key` is what's written to `watcher.listings.bike_key` so listings
    can be joined back to the catalog row by the web UI.
    """
    catalog_key: str
    make: str
    model: str
    year_start: int
    year_end: int
    webike_url: str | None = None
    aliases: list[str] = field(default_factory=list)

    @property
    def display_year(self) -> str:
        if self.year_start == 0 and self.year_end == 0:
            return ""  # year unknown — caller should omit
        if self.year_start == self.year_end:
            return str(self.year_start)
        return f"{self.year_start}-{self.year_end}"

    @property
    def search_terms(self) -> list[str]:
        """Search terms an adapter can feed into a source's keyword search."""
        base = f"{self.make} {self.model}"
        head = f"{base} {self.display_year}".strip()
        terms = [head]
        terms.extend(f"{base} {alias}".strip() for alias in self.aliases)
        return terms


def load_active_bikes(session: Session) -> list[BikeRef]:
    """All bikes referenced by at least one user in console.user_bikes."""
    sql = text("""
        SELECT DISTINCT bc.catalog_key, bc.make, bc.model, bc.year_start, bc.year_end, bc.webike_url
        FROM watcher.bike_catalog bc
        JOIN console.user_bikes ub ON ub.bike_catalog_id = bc.id
        ORDER BY bc.make, bc.model, bc.year_start
    """)
    rows = session.execute(sql).mappings().all()
    return [_to_ref(row) for row in rows]


def load_bike_by_key(session: Session, catalog_key: str) -> BikeRef | None:
    sql = text("""
        SELECT catalog_key, make, model, year_start, year_end, webike_url
        FROM watcher.bike_catalog
        WHERE catalog_key = :key
    """)
    row = session.execute(sql, {"key": catalog_key}).mappings().first()
    return _to_ref(row) if row else None


def _to_ref(row) -> BikeRef:
    return BikeRef(
        catalog_key=row["catalog_key"],
        make=row["make"],
        model=row["model"],
        year_start=row["year_start"],
        year_end=row["year_end"],
        webike_url=row.get("webike_url"),
        aliases=[],
    )
