"""One-shot cleanup: drop existing watcher.listings rows that fail the same
relevance check the ingest layer now applies to keyword-search adapters.

Run dry by default — pass --apply to actually delete. listing_snapshots cascades.

Usage:
    python -m motorcycle_parts_watcher.scripts.purge_irrelevant_listings        # dry-run
    python -m motorcycle_parts_watcher.scripts.purge_irrelevant_listings --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.bikes import BikeRef
from motorcycle_parts_watcher.config import get_settings
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.relevance import is_relevant_for_bike


# Mirror services/crawl.py's keyword-search adapter set. Bike-scoped sources
# (webike, old_bike_barn, manual_search, ...) are exempt because their fitment
# is implicit in the URL the adapter visited, not in the title.
KEYWORD_SOURCES = (
    "ebay", "mercari", "monotaro", "goobike",
    "yahoo_auctions", "buyee", "webike_search",
)


def _load_bikes(session: Session) -> dict[str, BikeRef]:
    rows = session.execute(text("""
        SELECT catalog_key, make, model, year_start, year_end
          FROM watcher.bike_catalog
    """)).mappings().all()
    return {
        r["catalog_key"]: BikeRef(
            catalog_key=r["catalog_key"], make=r["make"], model=r["model"],
            year_start=r["year_start"], year_end=r["year_end"],
        )
        for r in rows
    }


def _scan(session: Session) -> list[tuple[int, str, str]]:
    bikes = _load_bikes(session)
    irrelevant: list[tuple[int, str, str]] = []  # (id, bike_key, source_name)
    rows = session.execute(text("""
        SELECT id, bike_key, source_name, title, description, fitment_text
          FROM watcher.listings
         WHERE source_name = ANY(:srcs)
    """), {"srcs": list(KEYWORD_SOURCES)}).mappings()
    for r in rows:
        bike = bikes.get(r["bike_key"])
        if bike is None:
            # Orphaned bike_key (catalog row deleted) — leave it; not our problem.
            continue
        listing = NormalizedListing(
            source_name=r["source_name"], source_item_id="x", bike_key=r["bike_key"],
            title=r["title"] or "", description=r["description"],
            fitment_text=r["fitment_text"], url="https://x",
        )
        if not is_relevant_for_bike(listing, bike):
            irrelevant.append((r["id"], r["bike_key"], r["source_name"]))
    return irrelevant


def _summarize(irrelevant: list[tuple[int, str, str]]) -> None:
    by_source: dict[str, int] = defaultdict(int)
    by_bike: dict[str, int] = defaultdict(int)
    for _id, bike_key, source in irrelevant:
        by_source[source] += 1
        by_bike[bike_key] += 1
    print(f"\nTotal irrelevant rows: {len(irrelevant)}\n")
    print("By source:")
    for src, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
        print(f"  {src:<16} {n:>6}")
    print("\nBy bike (top 15):")
    for bk, n in sorted(by_bike.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {bk:<40} {n:>6}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually DELETE rows. Without this, just report counts.")
    ap.add_argument("--limit-print", type=int, default=20,
                    help="How many sample dropped titles to print (default 20).")
    args = ap.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    with Session(engine, autoflush=False) as session:
        irrelevant = _scan(session)
        _summarize(irrelevant)

        if args.limit_print and irrelevant:
            print(f"\nSample (first {args.limit_print}):")
            ids = [r[0] for r in irrelevant[:args.limit_print]]
            samples = session.execute(text("""
                SELECT id, source_name, bike_key, LEFT(title, 90) AS title
                  FROM watcher.listings WHERE id = ANY(:ids)
            """), {"ids": ids}).mappings().all()
            for s in samples:
                print(f"  [{s['source_name']:<14}] {s['bike_key']:<36} {s['title']}")

        if not args.apply:
            print("\nDry run — no changes written. Re-run with --apply to delete.")
            return 0

        if not irrelevant:
            print("\nNothing to delete.")
            return 0

        ids = [r[0] for r in irrelevant]
        deleted = session.execute(
            text("DELETE FROM watcher.listings WHERE id = ANY(:ids)"),
            {"ids": ids},
        ).rowcount
        session.commit()
        print(f"\nDeleted {deleted} listings (snapshots cascade).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
