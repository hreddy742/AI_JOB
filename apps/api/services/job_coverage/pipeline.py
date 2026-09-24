"""Job Coverage Engine ingestion pipeline."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.company_crawl_target import CompanyCrawlTarget
from services.ingestion.streams import push_job_to_stream
from services.job_coverage.connector_catalog import TIER1_SOURCES, fetch_tier1_jobs, fetch_tier2_jobs
from services.job_coverage.metrics import incr_source_metric, set_freshness_latency

logger = logging.getLogger(__name__)


async def enqueue_tier1_source(
    tenant_id: UUID,
    source: str,
    *,
    query: str = "",
    location: str | None = "United States",
    filters: dict[str, Any] | None = None,
) -> dict[str, int]:
    if source not in TIER1_SOURCES:
        raise KeyError(source)

    jobs = await fetch_tier1_jobs(source, query=query, location=location, filters=filters)
    emitted = 0
    failures = 0
    now = datetime.now(UTC)
    for posting in jobs:
        try:
            normalized = posting.to_normalized_job(tenant_id)
            await push_job_to_stream(normalized.model_dump(mode="json"), source)
            emitted += 1
            if posting.posted_at is not None:
                await set_freshness_latency(source, (now - posting.posted_at.astimezone(UTC)).total_seconds())
        except Exception:
            failures += 1
            logger.exception("job_coverage_tier1_enqueue_failed", extra={"extra": {"source": source}})

    await incr_source_metric(source, "jobs_ingested_per_source", emitted)
    if failures:
        await incr_source_metric(source, "jobs_failed_per_source", failures)
    return {"emitted": emitted, "failed": failures}


async def enqueue_tier2_target(tenant_id: UUID, target: CompanyCrawlTarget, *, html: str | None = None) -> dict[str, int]:
    if target.ats_type == "unknown":
        return {"emitted": 0, "failed": 0}

    jobs = await fetch_tier2_jobs(
        target.ats_type,
        careers_url=target.careers_url,
        company_domain=target.domain,
        html=html,
    )
    emitted = 0
    failures = 0
    for posting in jobs:
        try:
            normalized = posting.to_normalized_job(tenant_id)
            await push_job_to_stream(normalized.model_dump(mode="json"), posting.source)
            emitted += 1
        except Exception:
            failures += 1
            logger.exception("job_coverage_tier2_enqueue_failed", extra={"extra": {"ats": target.ats_type}})

    await incr_source_metric(target.ats_type, "jobs_ingested_per_source", emitted)
    if failures:
        await incr_source_metric(target.ats_type, "jobs_failed_per_source", failures)
    return {"emitted": emitted, "failed": failures}


async def enqueue_due_company_targets(db: AsyncSession, tenant_id: UUID, *, limit: int = 50) -> dict[str, int]:
    rows = (
        await db.execute(
            select(CompanyCrawlTarget)
            .where(CompanyCrawlTarget.tenant_id == tenant_id, CompanyCrawlTarget.is_active.is_(True))
            .order_by(CompanyCrawlTarget.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    emitted = 0
    failed = 0
    for target in rows:
        result = await enqueue_tier2_target(tenant_id, target)
        emitted += result["emitted"]
        failed += result["failed"]
    return {"emitted": emitted, "failed": failed, "targets": len(rows)}
