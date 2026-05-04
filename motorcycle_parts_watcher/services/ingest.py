from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.models import Listing, ListingSnapshot
from motorcycle_parts_watcher.schemas import NormalizedListing
from motorcycle_parts_watcher.utils.categorizer import classify
from motorcycle_parts_watcher.utils.hashing import compute_content_hash
from motorcycle_parts_watcher.utils.similarity import title_similarity


class IngestService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ingest_listing(self, listing: NormalizedListing) -> Listing:
        now = datetime.now(timezone.utc)
        hit = classify(listing.title, listing.description)
        listing.category = hit.category
        if listing.subcategory is None:
            listing.subcategory = hit.subcategory
        listing.content_hash = compute_content_hash(listing)
        existing = self._find_existing(listing)

        if existing:
            existing.last_seen_at = now
            existing.price_amount = listing.price_amount
            existing.price_currency = listing.price_currency
            existing.shipping_amount = listing.shipping_amount
            existing.condition = listing.condition
            existing.listing_status = listing.listing_status
            existing.seller_name = listing.seller_name
            existing.seller_country = listing.seller_country
            existing.image_url = listing.image_url
            existing.raw_json = listing.raw_json
            existing.category = listing.category
            existing.subcategory = listing.subcategory
            existing.part_number = listing.part_number
            existing.fitment_text = listing.fitment_text
            target = existing
        else:
            target = Listing(
                source_name=listing.source_name,
                source_item_id=listing.source_item_id,
                bike_key=listing.bike_key,
                title=listing.title,
                description=listing.description,
                url=listing.url,
                image_url=listing.image_url,
                price_amount=listing.price_amount,
                price_currency=listing.price_currency,
                shipping_amount=listing.shipping_amount,
                seller_name=listing.seller_name,
                seller_country=listing.seller_country,
                condition=listing.condition,
                category=listing.category,
                subcategory=listing.subcategory,
                part_number=listing.part_number,
                fitment_text=listing.fitment_text,
                listing_status=listing.listing_status,
                first_seen_at=now,
                last_seen_at=now,
                raw_json=listing.raw_json,
                content_hash=listing.content_hash,
            )
            self.session.add(target)
            self.session.flush()

        self.session.add(
            ListingSnapshot(
                listing_id=target.id,
                checked_at=now,
                price_amount=listing.price_amount,
                availability_status=listing.listing_status,
                raw_json=listing.raw_json,
            )
        )
        return target

    def _find_existing(self, listing: NormalizedListing) -> Listing | None:
        # 1) source_item_id
        if listing.source_item_id:
            row = self.session.scalar(
                select(Listing).where(
                    Listing.source_name == listing.source_name,
                    Listing.source_item_id == listing.source_item_id,
                )
            )
            if row:
                return row

        # 2) URL
        row = self.session.scalar(select(Listing).where(Listing.url == listing.url))
        if row:
            return row

        # 3) title similarity among likely candidates
        title_row = self._match_by_title_similarity(listing)
        if title_row:
            return title_row

        # 4) content hash
        row = self.session.scalar(select(Listing).where(Listing.content_hash == listing.content_hash))
        if row:
            return row

        return None

    def _match_by_title_similarity(self, listing: NormalizedListing) -> Listing | None:
        candidate_stmt: Select[tuple[Listing]] = select(Listing).where(
            Listing.bike_key == listing.bike_key,
            or_(Listing.source_name == listing.source_name, Listing.source_name == "manual_search"),
        )
        candidates = self.session.scalars(candidate_stmt.limit(200)).all()
        for candidate in candidates:
            if title_similarity(candidate.title, listing.title) >= 0.92:
                return candidate
        return None

