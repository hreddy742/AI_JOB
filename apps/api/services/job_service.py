"""Job ingestion and persistence services."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.base import NormalizedJob
from core.config import settings
from db.models.job import Job
from services.embedding_service import store_job_embedding
from services.search_service import index_job

logger = logging.getLogger(__name__)

POSITIVE_PATTERNS = [
    r"visa sponsorship",
    r"h[-\s]?1b",
    r"opt[\s/]cpt",
    r"work authorization provided",
    r"willing to sponsor",
    r"sponsorship available",
    r"relocation assistance",
]
NEGATIVE_PATTERNS = [
    r"no sponsorship",
    r"must be (authorized|eligible to work)",
    r"us citizen(ship)? required",
    r"security clearance required",
    r"not able to sponsor",
    r"cannot sponsor",
    r"no visa",
]

DEFAULT_TENANT_JOBS: list[dict[str, Any]] = [
    {
        "title": "Senior Backend Engineer",
        "company": "Acme Cloud",
        "description": "Build Python APIs and distributed systems.",
        "location_city": "New York",
        "remote": True,
        "sponsorship_score": 0.75,
        "tags": ["python", "fastapi", "postgres"],
    },
    {
        "title": "Platform Engineer",
        "company": "Northstar Labs",
        "description": "Own infrastructure and CI/CD for microservices.",
        "location_city": "San Francisco",
        "remote": False,
        "sponsorship_score": 0.4,
        "tags": ["kubernetes", "terraform", "aws"],
    },
    {
        "title": "Full Stack Engineer",
        "company": "Blue Orbit",
        "description": "Build React and FastAPI features for SaaS product.",
        "location_city": "Remote",
        "remote": True,
        "sponsorship_score": 0.6,
        "tags": ["react", "typescript", "python"],
    },
    {
        "title": "Data Engineer",
        "company": "Quantum Retail",
        "description": "Develop ETL pipelines and analytics models.",
        "location_city": "Austin",
        "remote": True,
        "sponsorship_score": 0.55,
        "tags": ["sql", "dbt", "airflow"],
    },
    {
        "title": "Software Engineer II",
        "company": "Nova Payments",
        "description": "Implement backend payment services and APIs.",
        "location_city": "Chicago",
        "remote": False,
        "sponsorship_score": 0.35,
        "tags": ["java", "spring", "postgres"],
    },
]


def get_redis_client() -> redis.Redis:
    """Return async Redis client."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def generate_fingerprint(job: NormalizedJob) -> str:
    """Generate deterministic content fingerprint for deduplication."""

    content = "|".join(
        [
            job.source.strip().lower(),
            job.source_id.strip().lower(),
            job.title.strip().lower(),
            job.company.strip().lower(),
            (job.url or "").strip().lower(),
        ]
    )
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> set[str]:
    """Tokenize and normalize text into unique tokens."""

    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity for two token sets."""

    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


async def is_near_duplicate(description: str | None, redis_client: redis.Redis, threshold: float = 0.9) -> bool:
    """Check recent-window near duplicates using Jaccard similarity."""

    if not description:
        return False
    target = _tokenize(description)
    entries = await redis_client.lrange("neardup:descriptions", 0, 199)
    for raw in entries:
        try:
            payload = json.loads(raw)
            existing_tokens = set(payload.get("tokens", []))
            if _jaccard(target, existing_tokens) >= threshold:
                return True
        except (json.JSONDecodeError, TypeError):
            continue
    return False


async def add_to_neardup_window(fingerprint: str, description: str | None, redis_client: redis.Redis) -> None:
    """Add normalized tokenized description to near-dup redis list."""

    if not description:
        return
    payload = json.dumps({"fingerprint": fingerprint, "tokens": sorted(_tokenize(description))})
    await redis_client.lpush("neardup:descriptions", payload)
    await redis_client.ltrim("neardup:descriptions", 0, 199)


def calculate_sponsorship_score(title: str, description: str) -> float:
    """Calculate sponsorship likelihood based on heuristic patterns."""

    text = (title + " " + description).lower()
    pos = sum(1 for pattern in POSITIVE_PATTERNS if re.search(pattern, text))
    neg = sum(1 for pattern in NEGATIVE_PATTERNS if re.search(pattern, text))
    if neg > 0:
        return max(0.0, 0.3 - (neg * 0.15))
    if pos > 0:
        return min(1.0, 0.5 + (pos * 0.15))
    return 0.5


async def enqueue_embedding_task(job_id: str, description: str, chroma_client: Any) -> None:
    """Enqueue non-blocking embedding store task."""

    async def _run() -> None:
        try:
            await store_job_embedding(job_id, description, chroma_client)
        except Exception:
            logger.exception("embedding_job_store_failed", extra={"extra": {"job_id": job_id}})

    asyncio.create_task(_run())


async def upsert_job(
    job: NormalizedJob,
    db: AsyncSession,
    typesense_client: Any,
    chroma_client: Any,
) -> bool:
    """Insert unique jobs and sync search + embeddings."""

    if job.tenant_id is None:
        raise ValueError("tenant_id is required for job upsert")

    redis_client = get_redis_client()
    scoped_source_id = f"{job.tenant_id}:{job.source_id}"
    fp = generate_fingerprint(job)

    source_existing = await db.execute(
        select(Job).where(Job.source == job.source, Job.source_id == scoped_source_id)
    )
    source_existing_job = source_existing.scalar_one_or_none()
    if source_existing_job is not None:
        await db.execute(
            update(Job)
            .where(Job.id == source_existing_job.id)
            .values(last_seen_at=datetime.now(UTC), is_active=True)
        )
        await db.commit()
        return False

    existing = await db.execute(select(Job).where(Job.fingerprint == fp, Job.tenant_id == job.tenant_id))
    existing_job = existing.scalar_one_or_none()
    if existing_job is not None:
        await db.execute(
            update(Job)
            .where(Job.id == existing_job.id)
            .values(last_seen_at=datetime.now(UTC), is_active=True)
        )
        await db.commit()
        return False

    if await is_near_duplicate(job.description, redis_client):
        return False

    posted_at_dt = datetime.fromtimestamp(job.posted_at, tz=UTC) if job.posted_at else None
    expires_at_dt = datetime.fromtimestamp(job.expires_at, tz=UTC) if job.expires_at else None

    sponsorship_score = calculate_sponsorship_score(job.title, job.description or "")

    new_job = Job(
        tenant_id=job.tenant_id,
        source=job.source,
        source_id=scoped_source_id,
        fingerprint=fp,
        title=job.title,
        company=job.company,
        description=job.description,
        url=job.url,
        location_city=job.location_city,
        location_state=job.location_state,
        location_country=job.location_country,
        remote=job.remote,
        sponsorship_score=sponsorship_score,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        job_type=job.job_type,
        experience_level=job.experience_level,
        tags=job.tags,
        posted_at=posted_at_dt,
        expires_at=expires_at_dt,
        raw_json=job.raw_json,
    )
    db.add(new_job)
    await db.flush()

    await index_job(
        {
            "id": new_job.id,
            "tenant_id": new_job.tenant_id,
            "title": new_job.title,
            "company": new_job.company,
            "description": new_job.description,
            "location_city": new_job.location_city,
            "location_state": new_job.location_state,
            "location_country": new_job.location_country,
            "remote": new_job.remote,
            "job_type": new_job.job_type.value if hasattr(new_job.job_type, "value") else str(new_job.job_type),
            "experience_level": new_job.experience_level.value if hasattr(new_job.experience_level, "value") else str(new_job.experience_level),
            "tags": new_job.tags,
            "salary_min": new_job.salary_min,
            "salary_max": new_job.salary_max,
            "sponsorship_score": new_job.sponsorship_score,
            "posted_at": new_job.posted_at,
            "source": new_job.source,
            "is_active": new_job.is_active,
        },
        typesense_client,
    )
    new_job.typesense_synced = True

    if settings.ENABLE_JOB_EMBEDDINGS and (job.description or "").strip():
        await enqueue_embedding_task(str(new_job.id), job.description or "", chroma_client)
    await add_to_neardup_window(fp, job.description, redis_client)

    await db.commit()
    return True


async def seed_default_jobs_for_tenant(db: AsyncSession, tenant_id: UUID, typesense_client: Any) -> int:
    """Create baseline job listings for a new tenant and sync them to Typesense."""

    created = 0
    now = datetime.now(UTC)
    for idx, spec in enumerate(DEFAULT_TENANT_JOBS, start=1):
        source_id = f"seed-{tenant_id}-{idx}"
        exists = await db.execute(select(Job.id).where(Job.source == "seed", Job.source_id == source_id))
        if exists.scalar_one_or_none() is not None:
            continue

        job = Job(
            tenant_id=tenant_id,
            source="seed",
            source_id=source_id,
            fingerprint=hashlib.md5(source_id.encode("utf-8")).hexdigest(),
            title=spec["title"],
            company=spec["company"],
            description=spec["description"],
            url=f"https://example.com/jobs/{source_id}",
            location_city=spec["location_city"],
            location_country="US",
            remote=spec["remote"],
            sponsorship_score=spec["sponsorship_score"],
            tags=spec["tags"],
            posted_at=now,
            raw_json={},
        )
        db.add(job)
        await db.flush()

        await index_job(
            {
                "id": job.id,
                "tenant_id": job.tenant_id,
                "title": job.title,
                "company": job.company,
                "description": job.description,
                "location_city": job.location_city,
                "location_state": job.location_state,
                "location_country": job.location_country,
                "remote": job.remote,
                "job_type": job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
                "experience_level": job.experience_level.value if hasattr(job.experience_level, "value") else str(job.experience_level),
                "tags": job.tags,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "sponsorship_score": job.sponsorship_score,
                "posted_at": job.posted_at,
                "source": job.source,
                "is_active": job.is_active,
            },
            typesense_client,
        )
        job.typesense_synced = True
        created += 1
    return created
