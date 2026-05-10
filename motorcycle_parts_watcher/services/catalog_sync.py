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
from datetime import UTC, datetime
from typing import Iterable
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.config import Settings
from motorcycle_parts_watcher.models import BikeCatalog, Category
from motorcycle_parts_watcher.utils.http import AsyncRateLimiter, build_async_client, with_retries


logger = logging.getLogger(__name__)

WEBIKE_BASE = "https://www.webike.tw"
USER_AGENT = "Mozilla/5.0 (compatible; motorcycle-parts-watcher/0.1; +catalog-sync)"

# Fallback list used only when the home-page discovery fetch fails.
DEFAULT_MAKES = ("HONDA", "YAMAHA", "SUZUKI", "KAWASAKI")

# Maker slugs are uppercase + digits + `-` / `_` (e.g. HARLEY-DAVIDSON, TW_SUZUKI).
_MF_LINK_RE = re.compile(r"/mf/([A-Z][A-Z0-9_-]*)/")

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
    variants_upserted: int = 0
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
    image_url: str | None = None

    @property
    def catalog_key(self) -> str:
        # year_start == 0 means "year unknown" (catalog index didn't expose year info).
        # In that case we omit the year suffix; otherwise include it.
        # Slugify the make so multi-word makes (e.g. "MV AGUSTA") yield a URL-safe key.
        # For single-token uppercase makes (HONDA, HARLEY-DAVIDSON) this matches `.lower()`.
        make_slug = _slugify(self.make)
        if self.year_start == 0 and self.year_end == 0:
            return f"{make_slug}-{self.model_slug}"
        if self.year_start == self.year_end:
            return f"{make_slug}-{self.model_slug}-{self.year_start}"
        return f"{make_slug}-{self.model_slug}-{self.year_start}-{self.year_end}"


def _slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _parse_extra_makes(raw: str) -> tuple[str, ...]:
    """Comma-separated WEBIKE_CATALOG_EXTRA_MAKES → uppercase slugs.

    Split on commas only — some webike slugs contain spaces (e.g. ``MV AGUSTA``,
    ``ROYAL ENFIELD``), so we cannot split on whitespace.
    """
    if not raw:
        return ()
    parts = (p.strip() for p in raw.split(","))
    return tuple(p.upper() for p in parts if p)


async def _discover_makes(settings: Settings, limiter: AsyncRateLimiter, client: httpx.AsyncClient) -> tuple[str, ...]:
    """Scrape the webike.tw home page for the full list of `/mf/{MAKE}/` slugs.

    Unions the result with `WEBIKE_CATALOG_EXTRA_MAKES` from settings — webike's
    homepage doesn't link every brand it actually hosts (e.g. KTM, MV Agusta).
    """
    extra = _parse_extra_makes(settings.webike_catalog_extra_makes)
    try:
        html = await _fetch_html(f"{WEBIKE_BASE}/", settings, limiter, client)
    except Exception as exc:
        print(f"[catalog-sync] make discovery fetch failed: {exc}; falling back to defaults", flush=True)
        seen: dict[str, None] = {m: None for m in DEFAULT_MAKES}
        for m in extra:
            seen.setdefault(m, None)
        return tuple(seen.keys())

    seen = {}  # ordered set
    for match in _MF_LINK_RE.finditer(html):
        seen.setdefault(match.group(1), None)
    if not seen:
        print("[catalog-sync] make discovery found no /mf/ links; falling back to defaults", flush=True)
        for m in DEFAULT_MAKES:
            seen.setdefault(m, None)
    for m in extra:
        seen.setdefault(m, None)
    return tuple(seen.keys())


async def sync_catalog(session: Session, settings: Settings) -> SyncStats:
    """Run a full catalog + taxonomy sync. Returns aggregate stats."""
    stats = SyncStats()

    print("[catalog-sync] starting", flush=True)
    limiter = AsyncRateLimiter(settings.http_rate_limit_per_second)

    async with build_async_client(settings) as client:
        makes = await _discover_makes(settings, limiter, client)
        print(f"[catalog-sync] makes ({len(makes)} discovered): {', '.join(makes)}", flush=True)

        # Categories first — cheap and synchronous.
        upserted = _upsert_taxonomy(session)
        stats.categories_upserted = upserted
        print(f"[catalog-sync] categories upserted: {upserted}", flush=True)
        session.commit()

        # Bikes — concurrent fan-out across all (make, cc-bucket) pairs.
        # asyncio is single-threaded so the shared session and seen_keys set are safe;
        # there are no await points between the seen_keys check+add or between
        # _upsert_bike calls, so neither can interleave with another coroutine.
        seen_keys: set[str] = set()
        current_year = datetime.now(UTC).year

        async def _process_bucket(make: str, slug: str, cc: int | None) -> None:
            # Some webike slugs contain spaces (e.g. "MV AGUSTA") — encode them.
            url = f"{WEBIKE_BASE}/mf/{quote(make, safe='-_')}/{slug}"
            try:
                html = await _fetch_html(url, settings, limiter, client)
            except Exception as exc:
                stats.fetch_errors += 1
                print(f"[catalog-sync] fetch failed {url}: {exc}", flush=True)
                return

            umbrellas: list[_BikeRow] = []
            for bike_row in _parse_bike_index(html, make, cc, base_url=url):
                if bike_row.catalog_key in seen_keys:
                    continue
                seen_keys.add(bike_row.catalog_key)
                _upsert_bike(session, bike_row)
                stats.bikes_upserted += 1
                umbrellas.append(bike_row)

            # Fan out variant fetches for all umbrellas in this bucket concurrently.
            counts = await asyncio.gather(
                *[_sync_md_variants(session, settings, limiter, client, u, current_year) for u in umbrellas],
                return_exceptions=True,
            )
            for r in counts:
                if isinstance(r, int):
                    stats.variants_upserted += r

            session.commit()
            print(
                f"[catalog-sync] {make}/{slug}: cumulative bikes={stats.bikes_upserted} "
                f"variants={stats.variants_upserted}",
                flush=True,
            )

        await asyncio.gather(*[
            _process_bucket(make, slug, cc)
            for make in makes
            for slug, cc in CC_BUCKETS
        ])

    print(
        f"[catalog-sync] done: bikes_upserted={stats.bikes_upserted} "
        f"variants_upserted={stats.variants_upserted} "
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


async def _fetch_html(url: str, settings: Settings, limiter: AsyncRateLimiter, client: httpx.AsyncClient) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    await limiter.wait()
    response = await with_retries(
        lambda: client.get(url, headers=headers),
        retries=settings.http_retries,
        backoff_seconds=settings.http_retry_backoff_seconds,
    )
    return response.text


_MD_LINK_RE = re.compile(r"/md/(\d+)")

# Year-range variants on a /md/{id} page. Each variant is wrapped in an anchor like:
#   <a ... href="/md/679/kt/3145" ...>年式 : 1981 ~ 1982 型式 : GS110X</a>
# The end-year may be blank (e.g. "2021 ~ ") for currently-produced models.
_VARIANT_LINK_RE = re.compile(
    r'<a[^>]*href="(/md/\d+/kt/\d+)"[^>]*>\s*年式\s*:\s*(\d{4})\s*~\s*(\d{4})?'
)


def _extract_bike_image(html: str) -> str | None:
    """Return the first CDN image URL from a webike.tw /md/{id} page, or None."""
    soup = BeautifulSoup(html, "lxml")
    img = soup.find("img", src=lambda s: s and "/moto_img/v3/" in s)
    if img:
        src = img.get("src", "")
        if src.startswith("//"):
            src = "https:" + src
        return src or None
    return None


def _parse_md_variants(html: str, base_md_url: str, current_year: int) -> list[tuple[int, int, str]]:
    """Pull `(year_start, year_end, deep_url)` rows from a /md/{id} model-line page.

    Each row corresponds to a production-year-range variant. Open-ended end-years
    (`年式 : 2021 ~  `) are filled with `current_year` so `yearsForModel` enumerates
    all years up to the present.
    """
    out: list[tuple[int, int, str]] = []
    seen_paths: set[str] = set()
    for match in _VARIANT_LINK_RE.finditer(html):
        path = match.group(1)
        if path in seen_paths:
            continue
        seen_paths.add(path)
        year_start = int(match.group(2))
        year_end = int(match.group(3)) if match.group(3) else current_year
        if year_end < year_start:
            year_end = year_start
        out.append((year_start, year_end, urljoin(base_md_url, path)))
    return out


def _parse_bike_index(html: str, make: str, displacement_cc: int | None, base_url: str) -> Iterable[_BikeRow]:
    """Pull bike model rows from a /mf/{MAKE}/{cc} index page.

    Each model is linked as `/md/{numeric_id}` with display text being the model name
    (e.g. "GSX-R1000", "ADDRESS V50"). Year info lives on the `/md/{id}` detail page;
    rows are emitted with `year_start = year_end = 0` ("umbrella") and the caller
    fans out to `_sync_md_variants` to add one row per year-range variant.
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


async def _sync_md_variants(
    session: Session,
    settings: Settings,
    limiter: AsyncRateLimiter,
    client: httpx.AsyncClient,
    umbrella: _BikeRow,
    current_year: int,
) -> int:
    """Fetch `/md/{id}` for an umbrella row and upsert one bike_catalog row per variant.

    Returns the number of variant rows upserted. Idempotent — variants share the
    umbrella's `(make, model, model_slug, displacement_cc)` and differ only in
    `(year_start, year_end, webike_url)`, which yields a stable `catalog_key`.
    """
    if not umbrella.webike_url:
        return 0
    try:
        html = await _fetch_html(umbrella.webike_url, settings, limiter, client)
    except Exception as exc:
        print(f"[catalog-sync] variant fetch failed {umbrella.webike_url}: {exc}", flush=True)
        return 0

    image_url = _extract_bike_image(html)
    variants = _parse_md_variants(html, umbrella.webike_url, current_year)
    for year_start, year_end, deep_url in variants:
        _upsert_bike(session, _BikeRow(
            make=umbrella.make,
            model=umbrella.model,
            model_slug=umbrella.model_slug,
            year_start=year_start,
            year_end=year_end,
            displacement_cc=umbrella.displacement_cc,
            webike_url=deep_url,
            image_url=image_url,
        ))
    return len(variants)


def _upsert_bike(session: Session, row: _BikeRow) -> None:
    now = datetime.now(UTC)
    update_cols: dict = dict(
        model=row.model,
        model_slug=row.model_slug,
        year_start=row.year_start,
        year_end=row.year_end,
        updated_at=now,
    )
    if row.displacement_cc is not None:
        update_cols["displacement_cc"] = row.displacement_cc
    if row.webike_url:
        update_cols["webike_url"] = row.webike_url
    if row.image_url:
        update_cols["image_url"] = row.image_url

    stmt = (
        pg_insert(BikeCatalog)
        .values(
            make=row.make,
            model=row.model,
            model_slug=row.model_slug,
            year_start=row.year_start,
            year_end=row.year_end,
            displacement_cc=row.displacement_cc,
            webike_url=row.webike_url,
            image_url=row.image_url,
            catalog_key=row.catalog_key,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_bike_catalog_key",
            set_=update_cols,
        )
    )
    session.execute(stmt)


def run_sync(session: Session, settings: Settings) -> SyncStats:
    """Sync entrypoint for non-async callers (CLI)."""
    return asyncio.run(sync_catalog(session, settings))
