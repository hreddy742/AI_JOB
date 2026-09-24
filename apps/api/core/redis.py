"""Shared async Redis connection pool for the entire application.

All modules should import `get_redis` from here instead of creating
their own per-request redis.from_url() clients. This prevents connection
exhaustion under load.
"""

from __future__ import annotations

import logging
from typing import Any

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    """Return (and lazily create) the shared connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _pool


def get_redis() -> aioredis.Redis:
    """Return an async Redis client backed by the shared pool.

    Callers must NOT call .close() on the returned client — the pool
    manages connection lifetime.
    """
    return aioredis.Redis(connection_pool=_get_pool())


async def redis_set(key: str, value: Any, ex: int | None = None) -> None:
    """Convenience wrapper: set a key, swallow transient errors."""
    try:
        client = get_redis()
        import json as _json
        serialised = value if isinstance(value, str) else _json.dumps(value)
        await client.set(key, serialised, ex=ex)
    except Exception as exc:
        logger.warning("redis_set_failed", extra={"extra": {"key": key, "error": str(exc), "error_type": type(exc).__name__}})


async def redis_get(key: str) -> str | None:
    """Convenience wrapper: get a key, return None on error."""
    try:
        return await get_redis().get(key)
    except Exception as exc:
        logger.warning("redis_get_failed", extra={"extra": {"key": key, "error": str(exc), "error_type": type(exc).__name__}})
        return None
