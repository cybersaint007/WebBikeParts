from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.models import Listing


def export_listings(session: Session, fmt: str) -> Path:
    rows = session.scalars(select(Listing).order_by(Listing.last_seen_at.desc())).all()
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        out = out_dir / "export.csv"
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "id",
                    "source_name",
                    "source_item_id",
                    "bike_key",
                    "title",
                    "url",
                    "price_amount",
                    "price_currency",
                    "condition",
                    "category",
                    "listing_status",
                    "first_seen_at",
                    "last_seen_at",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "id": row.id,
                        "source_name": row.source_name,
                        "source_item_id": row.source_item_id,
                        "bike_key": row.bike_key,
                        "title": row.title,
                        "url": row.url,
                        "price_amount": row.price_amount,
                        "price_currency": row.price_currency,
                        "condition": row.condition,
                        "category": row.category,
                        "listing_status": row.listing_status,
                        "first_seen_at": row.first_seen_at.isoformat(),
                        "last_seen_at": row.last_seen_at.isoformat(),
                    }
                )
        return out

    out = out_dir / "export.json"
    out.write_text(
        json.dumps(
            [
                {
                    "id": row.id,
                    "source_name": row.source_name,
                    "source_item_id": row.source_item_id,
                    "bike_key": row.bike_key,
                    "title": row.title,
                    "description": row.description,
                    "url": row.url,
                    "image_url": row.image_url,
                    "price_amount": str(row.price_amount) if row.price_amount is not None else None,
                    "price_currency": row.price_currency,
                    "shipping_amount": str(row.shipping_amount) if row.shipping_amount is not None else None,
                    "seller_name": row.seller_name,
                    "seller_country": row.seller_country,
                    "condition": row.condition,
                    "category": row.category,
                    "subcategory": row.subcategory,
                    "part_number": row.part_number,
                    "fitment_text": row.fitment_text,
                    "listing_status": row.listing_status,
                    "first_seen_at": row.first_seen_at.isoformat(),
                    "last_seen_at": row.last_seen_at.isoformat(),
                }
                for row in rows
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return out

