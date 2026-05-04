# Repository Guidelines

## Project Structure & Module Organization
- Main package: `motorcycle_parts_watcher/`
  - `adapters/`: source connectors (`ebay.py`, optional `yahoo_auctions.py`, `webike.py`, `manual_search.py`)
  - `services/`: business workflows (crawl, ingest, reporting, exporting, bootstrap, migrations)
  - `utils/`: shared helpers (HTTP retry/rate limit, categorization, hashing, similarity)
  - `models.py`: SQLAlchemy ORM models
  - `schemas.py`: Pydantic normalized data models
  - `cli.py`: Typer CLI entrypoint (`parts-watch`)
- Migrations: `alembic/` and `alembic/versions/`
- Tests: `tests/`
- Outputs/docs: `reports/`, `openclaw/tasks/`, root `*.md` guides

## Build, Test, and Development Commands
- Install deps: `python3 -m pip install '.[dev]'`
- Run tests: `python3 -m pytest -q`
- Apply migrations: `python3 -m alembic upgrade head`
- Initialize seed data: `parts-watch init-db`
- Crawl all sources/bikes: `parts-watch crawl-all`
- Generate reports:
  - `parts-watch report --format markdown`
  - `parts-watch report --format html`
- Export listings:
  - `parts-watch export --format csv`
  - `parts-watch export --format json`

## Coding Style & Naming Conventions
- Python 3.12 target, 4-space indentation, PEP 8 style.
- Use full type hints on public functions and service methods.
- Filenames/functions/variables: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE`.
- Keep adapters focused on fetch/normalize; keep dedupe/storage logic in `services/ingest.py`.

## Testing Guidelines
- Framework: `pytest` (with `pytest-asyncio` available).
- Test files: `tests/test_*.py`; test names: `test_*`.
- Add/adjust tests for any behavior changes in categorization, dedupe, reporting, exports, or CLI flows.
- Prefer small, deterministic unit tests over network-dependent tests.

## Security & Configuration Tips
- PostgreSQL only. Set:
  - `DATABASE_URL=postgresql+psycopg://...`
  - `DB_SCHEMA=watcher`
- Never commit real credentials or tokens. Use `.env` locally and keep `.env.example` sanitized.

## Commit & Pull Request Guidelines
- No Git history is currently available in this workspace; use clear, imperative commit messages (recommended: Conventional Commits, e.g., `feat: add ebay retry backoff`).
- PRs should include: purpose, scope, migration impact, test results, and sample CLI/report output when behavior changes.
