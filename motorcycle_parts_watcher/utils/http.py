from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from motorcycle_parts_watcher.config import Settings


class AsyncRateLimiter:
    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second if per_second > 0 else 0
        self._lock = asyncio.Lock()
        self._next_allowed = datetime.now(timezone.utc)

    async def wait(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = datetime.now(timezone.utc)
            if now < self._next_allowed:
                await asyncio.sleep((self._next_allowed - now).total_seconds())
            self._next_allowed = datetime.now(timezone.utc) + timedelta(seconds=self._interval)


async def with_retries(
    fn: Callable[[], Awaitable[httpx.Response]],
    retries: int,
    backoff_seconds: float,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = await fn()
            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == retries:
                break
            await asyncio.sleep(backoff_seconds * attempt)
    raise RuntimeError("HTTP request failed after retries") from last_error


def build_async_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.http_timeout_seconds, follow_redirects=True)


def parse_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
