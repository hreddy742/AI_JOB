"""Cross-source MinHash LSH deduplication."""

from __future__ import annotations

import json
import re
import asyncio
from collections import defaultdict

from core.redis import get_redis
from services.dedup_service import MinHashDeduplicator
from db.models.job import Job
from db.session import AsyncSessionFactory
from sqlalchemy import select

COMPANY_ALIASES = {
    "google llc": "google",
    "alphabet inc": "google",
    "alphabet": "google",
    "meta platforms": "meta",
    "meta platforms inc": "meta",
    "facebook": "meta",
    "amazon web services": "amazon",
    "aws": "amazon",
    "microsoft corporation": "microsoft",
    "apple inc": "apple",
    "netflix inc": "netflix",
}

_dedup = MinHashDeduplicator(threshold=0.75, num_perm=128)
_rebuild_lock = asyncio.Lock()
_rebuilt = False
_REDIS_KEY_PREFIX = "lsh:index"
_REDIS_TTL_SECONDS = 86400


def normalize_company(name: str) -> str:
    """Normalize company legal-name aliases."""

    cleaned = re.sub(r"[,.\-]", "", (name or "").lower().strip())
    return COMPANY_ALIASES.get(cleaned, cleaned)


def normalize_job_text(job: dict) -> str:
    """Normalize a job dict into dedup text representation."""

    tenant_scope = str(job.get("tenant_id", "")).strip().lower()
    company = normalize_company(str(job.get("company", "")))
    title = str(job.get("title", "")).lower().strip()
    location = str(job.get("location", job.get("location_city", ""))).lower().strip()
    description = str(job.get("description", ""))[:300].lower()
    # Include tenant scope so near-duplicate suppression does not cross tenant boundaries.
    return f"{tenant_scope} {title} {company} {location} {description}".strip()


def find_cross_source_duplicate(job_id: str, job: dict) -> str | None:
    """Return canonical job id when near-duplicate is found."""

    canonical, _score = _dedup.find_near_duplicate(job_id, normalize_job_text(job))
    return canonical


async def _load_lsh_from_redis() -> int:
    """Warm in-memory LSH from Redis snapshots keyed by tenant."""

    loaded = 0
    try:
        redis = get_redis()
        async for key in redis.scan_iter(match=f"{_REDIS_KEY_PREFIX}:*"):
            mapping = await redis.hgetall(key)
            for doc_id, payload_raw in mapping.items():
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    continue
                normalized = normalize_job_text(payload)
                _dedup.find_near_duplicate(doc_id, normalized)
                loaded += 1
                if loaded % 500 == 0:
                    await asyncio.sleep(0)
    except Exception:
        return 0
    return loaded


async def _persist_lsh_snapshot(rows_by_tenant: dict[str, dict[str, str]]) -> None:
    """Persist LSH source payloads to Redis for warm process restarts."""

    try:
        redis = get_redis()
        for tenant_id, payload_by_job in rows_by_tenant.items():
            if not payload_by_job:
                continue
            key = f"{_REDIS_KEY_PREFIX}:{tenant_id}"
            await redis.hset(key, mapping=payload_by_job)
            await redis.expire(key, _REDIS_TTL_SECONDS)
    except Exception:
        return


async def rebuild_lsh_from_db() -> int:
    """Rebuild in-memory LSH index from existing jobs in Postgres."""

    count = 0
    rows_by_tenant: dict[str, dict[str, str]] = defaultdict(dict)
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                select(Job.id, Job.tenant_id, Job.title, Job.company, Job.location_city, Job.description).where(Job.is_active.is_(True))
            )
        ).all()
    for row in rows:
        job_id = str(row[0])
        payload = {
            "tenant_id": str(row[1]),
            "title": row[2] or "",
            "company": row[3] or "",
            "location": row[4] or "",
            "description": row[5] or "",
        }
        _dedup.find_near_duplicate(job_id, normalize_job_text(payload))
        rows_by_tenant[str(row[1])][job_id] = json.dumps(payload, ensure_ascii=True)
        count += 1
        # Rebuild can process tens of thousands of rows; yield periodically to keep API responsive.
        if count % 500 == 0:
            await asyncio.sleep(0)
    await _persist_lsh_snapshot(rows_by_tenant)
    return count


async def ensure_lsh_ready() -> None:
    """Initialize LSH index once per process before ingestion runs."""

    global _rebuilt
    if _rebuilt:
        return
    async with _rebuild_lock:
        if _rebuilt:
            return
        loaded = await _load_lsh_from_redis()
        if loaded == 0:
            await rebuild_lsh_from_db()
        _rebuilt = True
