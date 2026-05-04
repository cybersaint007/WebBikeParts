from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, MetaData, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from motorcycle_parts_watcher.config import get_settings


DB_SCHEMA = get_settings().db_schema


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(schema=DB_SCHEMA)


class Bike(Base):
    __tablename__ = "bikes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    variant: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    bike_catalog_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.bike_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )


class BikeCatalog(Base):
    __tablename__ = "bike_catalog"
    __table_args__ = (
        UniqueConstraint("catalog_key", name="uq_bike_catalog_key"),
        {"schema": DB_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    model_slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    year_start: Mapped[int] = mapped_column(nullable=False)
    year_end: Mapped[int] = mapped_column(nullable=False)
    displacement_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    webike_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    catalog_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        {"schema": DB_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    label_en: Mapped[str] = mapped_column(String(150), nullable=False)
    label_zh: Mapped[str | None] = mapped_column(String(150), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.categories.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    webike_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("url", name="uq_listings_url"),
        UniqueConstraint("source_name", "source_item_id", name="uq_listings_source_item"),
        {"schema": DB_SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    bike_key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_currency: Mapped[str | None] = mapped_column(String(10))
    shipping_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    seller_name: Mapped[str | None] = mapped_column(String(255))
    seller_country: Mapped[str | None] = mapped_column(String(100))
    condition: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False, default="unknown")
    subcategory: Mapped[str | None] = mapped_column(String(100))
    part_number: Mapped[str | None] = mapped_column(String(100), index=True)
    fitment_text: Mapped[str | None] = mapped_column(Text)
    listing_status: Mapped[str] = mapped_column(String(100), nullable=False, default="active")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    snapshots: Mapped[list["ListingSnapshot"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"
    __table_args__ = {"schema": DB_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    availability_status: Mapped[str | None] = mapped_column(String(100))
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    listing: Mapped[Listing] = relationship(back_populates="snapshots")
