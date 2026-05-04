"""Sync watcher.bike_catalog and watcher.categories from webike.tw.

Walks `https://www.webike.tw/mf/{MAKE}/{CC}` per make × CC bucket to discover
bikes; walks the category navigation to populate the taxonomy. Idempotent — every
run upserts and refreshes `scraped_at` / `updated_at`.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.models import BikeCatalog, Category
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, with_retries


logger = logging.getLogger(__name__)

WEBIKE_BASE = "https://www.webike.tw"
USER_AGENT = "Mozilla/5.0 (compatible; motorcycle-parts-watcher/0.1; +catalog-sync)"

# Default makes to walk; configurable via WEBIKE_CATALOG_MAKES env (comma-separated).
DEFAULT_MAKES = ("HONDA", "YAMAHA", "SUZUKI", "KAWASAKI")

# Webike's CC buckets for the /mf/{MAKE}/{cc} index. Each entry is (URL slug, displacement_cc).
# URL slugs are single numbers; the displacement is the upper bound of that bucket
# (e.g. /mf/SUZUKI/125 covers 51-125cc).
CC_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("50", 50),
    ("125", 125),
    ("250", 250),
    ("400", 400),
    ("750", 750),
    ("1000", 1000),
    ("1001", None),  # 1001cc+
)

# Top-level categories drawn from webike.tw nav.
TOP_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("modification",       "Modification Parts", "改裝零件"),
    ("oem",                "OEM Parts",          "原廠零件"),
    ("maintenance",        "Maintenance",        "保養耗材"),
    ("gear",               "Rider Gear",         "騎士用品"),
    ("tools",              "Tools",              "機車工具"),
)

SUBCATEGORIES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "modification": (
        ("modification-exhaust",      "Exhaust",      "排氣管"),
        ("modification-body",         "Body",         "外觀車殼"),
        ("modification-steering",     "Steering",     "操控"),
        ("modification-brakes",       "Brakes",       "煞車系統"),
        ("modification-engine",       "Engine",       "引擎"),
        ("modification-electrical",   "Electrical",   "電系系統"),
        ("modification-chassis",      "Chassis",      "車架"),
        ("modification-transmission", "Transmission", "傳動"),
    ),
    "maintenance": (
        ("maintenance-oils",      "Oils",         "機油"),
        ("maintenance-tires",     "Tires",        "輪胎"),
        ("maintenance-batteries", "Batteries",    "電池"),
        ("maintenance-repair",    "Repair Parts", "維修零件"),
    ),
    "gear": (
        ("gear-helmets", "Helmets",  "安全帽"),
        ("gear-apparel", "Apparel",  "騎士服飾"),
        ("gear-boots",   "Boots",    "騎士車靴"),
    ),
    "tools": (
        ("tools-hand",      "Hand Tools",      "手工具"),
        ("tools-power",     "Power Tools",     "電動工具"),
        ("tools-specialty", "Specialty Tools", "專用工具"),
    ),
}


@dataclass
class SyncStats:
    bikes_upserted: int = 0
    categories_upserted: int = 0
    fetch_errors: int = 0


@dataclass
class _BikeRow:
    make: str
    model: str
    model_slug: str
    year_start: int
    year_end: int
    displacement_cc: int | None
    webike_url: str | None

    @property
    def catalog_key(self) -> str:
        # year_start == 0 means "year unknown" (catalog index didn't expose year info).
        # In that case we omit the year suffix; otherwise include it.
        if self.year_start == 0 and self.year_end == 0:
            return f"{self.make.lower()}-{self.model_slug}"
        if self.year_start == self.year_end:
            return f"{self.make.lower()}-{self.model_slug}-{self.year_start}"
        return f"{self.make.lower()}-{self.model_slug}-{self.year_start}-{self.year_end}"


def _slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _resolve_makes(settings: Settings) -> tuple[str, ...]:
    raw = getattr(settings, "webike_catalog_makes", None) or ""
    if isinstance(raw, str) and raw.strip():
        return tuple(m.strip().upper() for m in raw.split(",") if m.strip())
    return DEFAULT_MAKES


async def sync_catalog(session: Session, settings: Settings) -> SyncStats:
    """Run a full catalog + taxonomy sync. Returns aggregate stats."""
    stats = SyncStats()

    print("[catalog-sync] starting", flush=True)
    makes = _resolve_makes(settings)
    print(f"[catalog-sync] makes: {', '.join(makes)}", flush=True)

    # Categories first — cheap and synchronous.
    upserted = _upsert_taxonomy(session)
    stats.categories_upserted = upserted
    print(f"[catalog-sync] categories upserted: {upserted}", flush=True)
    session.commit()

    # Bikes — async fan-out per (make, cc bucket).
    limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)
    seen_keys: set[str] = set()

    for make in makes:
        for slug, cc in CC_BUCKETS:
            url = f"{WEBIKE_BASE}/mf/{make}/{slug}"
            try:
                html = await _fetch_html(url, settings, limiter)
            except Exception as exc:
                stats.fetch_errors += 1
                print(f"[catalog-sync] fetch failed {url}: {exc}", flush=True)
                continue

            for bike_row in _parse_bike_index(html, make, cc, base_url=url):
                if bike_row.catalog_key in seen_keys:
                    continue
                seen_keys.add(bike_row.catalog_key)
                _upsert_bike(session, bike_row)
                stats.bikes_upserted += 1

            print(f"[catalog-sync] {make}/{slug}: cumulative bikes={stats.bikes_upserted}", flush=True)
            session.commit()

    print(
        f"[catalog-sync] done: bikes_upserted={stats.bikes_upserted} "
        f"categories_upserted={stats.categories_upserted} fetch_errors={stats.fetch_errors}",
        flush=True,
    )
    return stats


def _upsert_taxonomy(session: Session) -> int:
    """Insert/update the static webike-mirrored taxonomy. Returns number of rows touched."""
    touched = 0
    existing = {c.slug: c for c in session.scalars(select(Category)).all()}

    for slug, label_en, label_zh in TOP_CATEGORIES:
        cat = existing.get(slug)
        if cat is None:
            cat = Category(slug=slug, label_en=label_en, label_zh=label_zh)
            session.add(cat)
            existing[slug] = cat
        else:
            cat.label_en = label_en
            cat.label_zh = label_zh
        touched += 1

    session.flush()  # ensure top-level rows have ids before subcategories reference them

    for parent_slug, subs in SUBCATEGORIES.items():
        parent = existing.get(parent_slug)
        if parent is None:
            continue
        for slug, label_en, label_zh in subs:
            cat = existing.get(slug)
            if cat is None:
                cat = Category(slug=slug, label_en=label_en, label_zh=label_zh, parent_id=parent.id)
                session.add(cat)
                existing[slug] = cat
            else:
                cat.label_en = label_en
                cat.label_zh = label_zh
                cat.parent_id = parent.id
            touched += 1

    return touched


async def _fetch_html(url: str, settings: Settings, limiter: AsyncRateLimiter) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    async with build_async_client(settings) as client:
        await limiter.wait()
        response = await with_retries(
            lambda: client.get(url, headers=headers),
            retries=settings.http_retries,
            backoff_seconds=settings.http_retry_backoff_seconds,
        )
    return response.text


_MD_LINK_RE = re.compile(r"/md/(\d+)")


def _parse_bike_index(html: str, make: str, displacement_cc: int | None, base_url: str) -> Iterable[_BikeRow]:
    """Pull bike model rows from a /mf/{MAKE}/{cc} index page.

    Each model is linked as `/md/{numeric_id}` with display text being the model name
    (e.g. "GSX-R1000", "ADDRESS V50"). Year info isn't on this page — it's on /md/{id}
    detail pages. For now we store year_start = year_end = 0 ("unknown") and let the
    catalog_key omit the year suffix. Future enhancement: fetch /md/{id} per model.
    """
    soup = BeautifulSoup(html, "lxml")
    seen_ids: set[str] = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        m = _MD_LINK_RE.search(href)
        if not m:
            continue
        md_id = m.group(1)
        if md_id in seen_ids:
            continue
        seen_ids.add(md_id)

        model_display = a.get_text(" ", strip=True)
        if not model_display or len(model_display) > 100:
            continue
        # Skip obvious non-model entries: numeric-only, "詳細", "加入MyBike", etc.
        if model_display.isdigit() or any(s in model_display for s in ("詳細", "加入", "MyBike", "更多", "全部")):
            continue

        model_slug = _slugify(model_display)
        if not model_slug or model_slug.isdigit():
            continue

        yield _BikeRow(
            make=make,
            model=model_display,
            model_slug=model_slug,
            year_start=0,
            year_end=0,
            displacement_cc=displacement_cc,
            webike_url=urljoin(base_url, href),
        )


def _upsert_bike(session: Session, row: _BikeRow) -> None:
    existing = session.scalar(select(BikeCatalog).where(BikeCatalog.catalog_key == row.catalog_key))
    if existing is None:
        session.add(BikeCatalog(
            make=row.make,
            model=row.model,
            model_slug=row.model_slug,
            year_start=row.year_start,
            year_end=row.year_end,
            displacement_cc=row.displacement_cc,
            webike_url=row.webike_url,
            catalog_key=row.catalog_key,
        ))
    else:
        existing.model = row.model
        existing.model_slug = row.model_slug
        existing.year_start = row.year_start
        existing.year_end = row.year_end
        if row.displacement_cc is not None:
            existing.displacement_cc = row.displacement_cc
        if row.webike_url:
            existing.webike_url = row.webike_url


def run_sync(session: Session, settings: Settings) -> SyncStats:
    """Sync entrypoint for non-async callers (CLI)."""
    return asyncio.run(sync_catalog(session, settings))
