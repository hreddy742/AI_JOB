"""Redis-backed rate limiting helpers."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import HTTPException, Request


async def check_rate_limit(
    redis: aioredis.Redis,
    key: str,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Increment request counter and raise if limit exceeded."""

    # Allow per-route disable via settings (e.g., login retries without time window).
    if max_attempts <= 0 or window_seconds <= 0:
        return

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    results = await pipe.execute()
    count = int(results[0])
    if count > max_attempts:
        ttl = int(await redis.ttl(key))
        if ttl < 0:
            ttl = window_seconds
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Too many attempts. Try again in {ttl} seconds.",
                "retry_after": ttl,
            },
            headers={"Retry-After": str(ttl)},
        )


def get_client_ip(request: Request) -> str:
    """Extract client IP honoring reverse-proxy headers."""

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"
