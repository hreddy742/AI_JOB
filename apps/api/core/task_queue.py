"""Shared helpers for ARQ enqueue paths.

These helpers intentionally keep the existing queue model and payload shapes.
They only centralize repeated boilerplate so worker launches are easier to
audit and behave more consistently across services.
"""

from __future__ import annotations

from typing import Any

try:
    from arq import create_pool
    from arq.connections import RedisSettings
except ModuleNotFoundError:  # pragma: no cover - import fallback for tests
    async def create_pool(*_args, **_kwargs):
        raise RuntimeError("arq is required for async queue operations")

    class RedisSettings:  # type: ignore[override]
        @classmethod
        def from_dsn(cls, _dsn: str):
            return cls()

from core.config import settings


async def enqueue_arq_job(
    function_name: str,
    *args: Any,
    queue_name: str,
    job_id: str | None = None,
    **kwargs: Any,
) -> None:
    """Enqueue one ARQ job with a consistent connection lifecycle.

    `job_id` is optional and only used for observability/idempotency-friendly
    tracing. Existing task IDs remain the source of truth for status lookups.
    """

    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        enqueue_kwargs: dict[str, Any] = {"_queue_name": queue_name}
        if job_id:
            enqueue_kwargs["_job_id"] = job_id
        await redis.enqueue_job(function_name, *args, **kwargs, **enqueue_kwargs)
    finally:
        await redis.close()
