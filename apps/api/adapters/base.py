"""Base adapter interfaces and shared ingestion utilities."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict


class NormalizedJob(BaseModel):
    """Normalized job shape used by ingestion and persistence."""

    model_config = ConfigDict(extra="ignore")

    tenant_id: UUID | None = None
    source: str
    source_id: str
    title: str
    company: str
    description: str | None = None
    url: str
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None
    remote: bool = False
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "USD"
    job_type: str = "unknown"
    experience_level: str = "unknown"
    tags: list[str] = []
    posted_at: float | None = None
    expires_at: float | None = None
    raw_json: dict[str, Any] | None = None


class TokenBucketRateLimiter:
    """Simple async token bucket limiter."""

    def __init__(self, calls_per_minute: int) -> None:
        self.capacity = max(calls_per_minute, 1)
        self.tokens = float(self.capacity)
        self.fill_rate = self.capacity / 60.0
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""

        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.updated_at = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                await asyncio.sleep(max((1.0 - self.tokens) / self.fill_rate, 0.05))


class BaseJobAdapter(ABC):
    """Abstract base adapter for job source providers."""

    SOURCE_NAME: str
    REFRESH_INTERVAL_SECONDS: int = 3600
    calls_per_minute: int = 30

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        self.api_key = api_key
        self.extra_config = kwargs
        self._rate_limiter = TokenBucketRateLimiter(self.calls_per_minute)
        self._client = httpx.AsyncClient(timeout=10.0)

    @abstractmethod
    async def _fetch_page(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch one page from source API."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        """Normalize source payload into internal job schema."""

    def _extract_items(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract item list from common API envelope patterns."""

        for key in ("results", "data", "jobs", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(raw.get("result"), list):
            return [item for item in raw["result"] if isinstance(item, dict)]
        if isinstance(raw.get("data"), dict) and isinstance(raw["data"].get("jobs"), list):
            return [item for item in raw["data"]["jobs"] if isinstance(item, dict)]
        if isinstance(raw, dict) and raw and all(isinstance(v, dict) for v in raw.values()):
            return [v for v in raw.values() if isinstance(v, dict)]
        return []

    async def search(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict[str, Any],
    ) -> AsyncGenerator[NormalizedJob, None]:
        """Search source and yield normalized jobs."""

        await self._rate_limiter.acquire()
        raw = await self._fetch_with_retry(query, location, page, page_size, filters)
        for item in self._extract_items(raw):
            yield self.normalize(item)

    async def _fetch_with_retry(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Fetch with backoff retries on 429 and 5xx."""

        delays = [5, 10, 20]
        for attempt in range(max_retries + 1):
            try:
                result = await self._fetch_page(query, location, page, page_size, filters)
                return result
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status == 429 or 500 <= status < 600
                if not retryable or attempt >= max_retries:
                    raise
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
            except httpx.RequestError:
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
        return {}

    async def close(self) -> None:
        """Close underlying HTTP client."""

        await self._client.aclose()
