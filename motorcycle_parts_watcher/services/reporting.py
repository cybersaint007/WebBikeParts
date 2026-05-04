from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from motorcycle_parts_watcher.models import Listing


@dataclass
class GroupedListings:
    bike: str
    category: str
    condition: str
    source: str
    items: list[Listing]


def _group_rows(rows: list[Listing]) -> list[GroupedListings]:
    grouped: dict[tuple[str, str, str, str], list[Listing]] = defaultdict(list)
    for row in rows:
        key = (row.bike_key, row.category or "unknown", row.condition or "unknown", row.source_name)
        grouped[key].append(row)
    return [
        GroupedListings(bike=bike, category=category, condition=condition, source=source, items=items)
        for (bike, category, condition, source), items in sorted(grouped.items(), key=lambda x: x[0])
    ]


def _markdown_from_groups(groups: list[GroupedListings], title: str) -> str:
    lines = [f"# {title}", ""]
    for group in groups:
        lines.append(f"## Bike: {group.bike}")
        lines.append(f"### Category: {group.category}")
        lines.append(f"#### Condition: {group.condition}")
        lines.append(f"##### Source: {group.source}")
        for item in group.items:
            price = f"{item.price_amount} {item.price_currency or ''}".strip() if item.price_amount is not None else "N/A"
            lines.append(f"- [{item.title}]({item.url}) | Price: {price} | Status: {item.listing_status}")
        lines.append("")
    return "\n".join(lines)


def _html_from_groups(groups: list[GroupedListings], title: str) -> str:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(default_for_string=True),
    )
    template = env.get_template("report.html.j2")
    return template.render(title=title, groups=groups)


def generate_reports(session: Session, fmt: str) -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows = session.scalars(select(Listing).order_by(Listing.last_seen_at.desc())).all()

    latest_groups = _group_rows(rows)
    if fmt == "markdown":
        (reports_dir / "latest.md").write_text(_markdown_from_groups(latest_groups, "Latest Listings"), encoding="utf-8")
        for bike_key in sorted({row.bike_key for row in rows}):
            bike_rows = [row for row in rows if row.bike_key == bike_key]
            groups = _group_rows(bike_rows)
            (reports_dir / f"{bike_key}.md").write_text(
                _markdown_from_groups(groups, f"Listings for {bike_key}"),
                encoding="utf-8",
            )
    elif fmt == "html":
        (reports_dir / "latest.html").write_text(_html_from_groups(latest_groups, "Latest Listings"), encoding="utf-8")
    else:
        raise ValueError("fmt must be markdown or html")
