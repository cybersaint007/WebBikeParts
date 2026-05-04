from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    database_url: str = Field(alias="DATABASE_URL")
    db_schema: str = Field(default="watcher", alias="DB_SCHEMA")
    ebay_enabled: bool = Field(default=True, alias="EBAY_ENABLED")
    ebay_client_id: str = Field(default="", alias="EBAY_CLIENT_ID")
    ebay_client_secret: str = Field(default="", alias="EBAY_CLIENT_SECRET")
    ebay_marketplace_id: str = Field(default="EBAY_US", alias="EBAY_MARKETPLACE_ID")
    ebay_marketplace_ids: str = Field(default="", alias="EBAY_MARKETPLACE_IDS")
    yahoo_auctions_enabled: bool = Field(default=False, alias="YAHOO_AUCTIONS_ENABLED")
    webike_enabled: bool = Field(default=False, alias="WEBIKE_ENABLED")
    webike_catalog_makes: str = Field(default="", alias="WEBIKE_CATALOG_MAKES")
    webike_jp_enabled: bool = Field(default=False, alias="WEBIKE_JP_ENABLED")
    croooober_enabled: bool = Field(default=False, alias="CROOOOBER_ENABLED")
    mercari_enabled: bool = Field(default=False, alias="MERCARI_ENABLED")
    rakuten_enabled: bool = Field(default=False, alias="RAKUTEN_ENABLED")
    rakuten_app_id: str = Field(default="", alias="RAKUTEN_APP_ID")
    monotaro_enabled: bool = Field(default=False, alias="MONOTARO_ENABLED")
    goobike_enabled: bool = Field(default=False, alias="GOOBIKE_ENABLED")
    manual_search_enabled: bool = Field(default=True, alias="MANUAL_SEARCH_ENABLED")
    http_timeout_seconds: float = Field(default=20, alias="HTTP_TIMEOUT_SECONDS")
    http_retries: int = Field(default=3, alias="HTTP_RETRIES")
    http_retry_backoff_seconds: float = Field(default=1.0, alias="HTTP_RETRY_BACKOFF_SECONDS")
    http_rate_limit_per_second: float = Field(default=3.0, alias="HTTP_RATE_LIMIT_PER_SECOND")
    default_currency: str = Field(default="USD", alias="DEFAULT_CURRENCY")

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL must use PostgreSQL with psycopg driver: "
                "postgresql+psycopg://..."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    data = {k: v for k, v in os.environ.items() if k.isupper()}
    return Settings.model_validate(data)
