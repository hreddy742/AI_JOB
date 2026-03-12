"""Health check endpoint for load balancers and monitoring."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from core.arq_queues import (
    QUEUE_AUTOMATION,
    QUEUE_CAMPAIGN,
    QUEUE_EMBEDDING,
    QUEUE_INGESTION,
    QUEUE_JOB_COVERAGE,
    QUEUE_JOB_DETAIL_ENRICHMENT,
    QUEUE_JOB_REQUIREMENTS,
    QUEUE_NOTIFICATION,
    QUEUE_REFERRAL,
    QUEUE_RESUME,
    QUEUE_TAILORING,
)
from core.config import settings
from core.redis import get_redis
from db.session import AsyncSessionFactory
from services.search_service import get_typesense_client

router = APIRouter(tags=["Health"])

_TYPESENSE_HEALTH_TIMEOUT_SECONDS = 2.5
_HTTP_DEPENDENCY_TIMEOUT_SECONDS = 3.0
_QUEUE_NAMES = [
    QUEUE_RESUME,
    QUEUE_TAILORING,
    QUEUE_AUTOMATION,
    QUEUE_CAMPAIGN,
    QUEUE_REFERRAL,
    QUEUE_EMBEDDING,
    QUEUE_JOB_REQUIREMENTS,
    QUEUE_JOB_DETAIL_ENRICHMENT,
    QUEUE_JOB_COVERAGE,
    QUEUE_INGESTION,
    QUEUE_NOTIFICATION,
]


async def _probe_http_json(url: str) -> bool:
    async with httpx.AsyncClient(timeout=_HTTP_DEPENDENCY_TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        response.raise_for_status()
    return True


async def _probe_minio() -> bool:
    endpoint = settings.MINIO_ENDPOINT.strip()
    if not endpoint:
        return False
    base = endpoint if endpoint.startswith("http://") or endpoint.startswith("https://") else f"http://{endpoint}"
    return await _probe_http_json(f"{base.rstrip('/')}/minio/health/live")


async def _probe_ollama() -> bool:
    return await _probe_http_json(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")


async def _probe_smtp() -> bool:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(settings.SMTP_HOST, settings.SMTP_PORT),
        timeout=_HTTP_DEPENDENCY_TIMEOUT_SECONDS,
    )
    del reader
    writer.close()
    await writer.wait_closed()
    return True


async def _queue_depths() -> dict[str, int]:
    redis = get_redis()
    depths: dict[str, int] = {}
    for queue_name in _QUEUE_NAMES:
        try:
            depths[queue_name] = int(await redis.zcard(queue_name) or 0)
        except Exception:
            depths[queue_name] = -1
    return depths


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check connectivity to PostgreSQL, Redis, and Typesense."""

    checks: dict[str, str] = {}
    overall = "healthy"

    # PostgreSQL
    try:
        async with AsyncSessionFactory() as db:
            await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {type(exc).__name__}"
        overall = "degraded"

    # Redis
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
        overall = "degraded"

    queue_depths: dict[str, int] = {}
    if checks.get("redis") == "ok":
        queue_depths = await _queue_depths()

    # Typesense
    try:
        client = get_typesense_client()

        def _probe_typesense() -> list[dict[str, Any]]:
            return client.collections.retrieve()

        health = await asyncio.wait_for(
            asyncio.to_thread(_probe_typesense),
            timeout=_TYPESENSE_HEALTH_TIMEOUT_SECONDS,
        )
        checks["typesense"] = "ok" if isinstance(health, list) else "degraded"
    except TimeoutError:
        checks["typesense"] = "error: TimeoutError"
        overall = "degraded"
    except Exception as exc:
        checks["typesense"] = f"error: {type(exc).__name__}"
        overall = "degraded"

    for dependency_name, probe in {
        "minio": _probe_minio,
        "ollama": _probe_ollama,
        "smtp": _probe_smtp,
    }.items():
        try:
            await probe()
            checks[dependency_name] = "ok"
        except Exception as exc:
            checks[dependency_name] = f"error: {type(exc).__name__}"
            overall = "degraded"

    return {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": settings.ENVIRONMENT,
        "queue_depths": queue_depths,
        **checks,
    }
