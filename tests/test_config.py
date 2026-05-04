import pytest
from pydantic import ValidationError

from motorcycle_parts_watcher.config import Settings


def test_settings_reject_non_postgres_url() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"DATABASE_URL": "sqlite:///tmp.db"})


def test_settings_accept_postgres_psycopg_url() -> None:
    settings = Settings.model_validate(
        {"DATABASE_URL": "postgresql+psycopg://user:password@localhost:5432/bike_parts_watcher"}
    )
    assert settings.database_url.startswith("postgresql+psycopg://")

