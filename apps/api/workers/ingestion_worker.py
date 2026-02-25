"""ARQ ingestion worker with per-source schedules."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import chromadb
from arq import cron
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.adzuna import AdzunaAdapter
from adapters.arbeitnow import ArbeitnowAdapter
from adapters.greenhouse_feed import GreenhouseFeedAdapter
from adapters.jobspy import JobSpyAdapter
from adapters.lever_feed import LeverFeedAdapter
from adapters.remoteok import RemoteOKAdapter
from adapters.the_muse import TheMuseAdapter
from adapters.usajobs import USAJobsAdapter
from core.config import settings
from db.models.supervisor_log import SupervisorLog
from db.models.tenant import Tenant
from db.session import AsyncSessionFactory
from services.job_service import upsert_job
from services.search_service import ensure_jobs_collection, get_typesense_client

logger = logging.getLogger(__name__)

ADAPTERS = {
    "greenhouse": GreenhouseFeedAdapter(),
    "lever": LeverFeedAdapter(),
    "remoteok": RemoteOKAdapter(),
    "adzuna": AdzunaAdapter(api_key=settings.ADZUNA_API_KEY, app_id=settings.ADZUNA_APP_ID),
    "arbeitnow": ArbeitnowAdapter(),
    "the_muse": TheMuseAdapter(api_key=settings.THE_MUSE_API_KEY),
    "usajobs": USAJobsAdapter(api_key=settings.USAJOBS_API_KEY),
    "jobspy": JobSpyAdapter(),
}


async def broadcast_new_job(job: object) -> None:
    """Broadcast hook for notifying clients about new jobs."""

    logger.info("new_job_broadcast", extra={"extra": {"source": getattr(job, "source", "unknown")}})


async def log_ingestion_run(source_name: str, ingested: int, db: AsyncSession, tenant_id: UUID) -> None:
    """Persist ingestion run metrics to supervisor logs."""

    db.add(
        SupervisorLog(
            tenant_id=tenant_id,
            event_type="ingestion_run",
            severity="info",
            payload={"source": source_name, "new_jobs": ingested, "ts": datetime.now(UTC).isoformat()},
        )
    )
    await db.commit()


async def ingest_source(ctx: dict, source_name: str) -> dict[str, object]:
    """Ingest jobs for one source and one tenant context."""

    adapter = ADAPTERS[source_name]
    db: AsyncSession = ctx["db"]
    typesense_client = ctx["typesense"]
    chroma_client = ctx["chroma"]
    tenant_id = ctx.get("tenant_id")

    if tenant_id is None:
        logger.warning("ingest_source_missing_tenant", extra={"extra": {"source": source_name}})
        return {"source": source_name, "new_jobs": 0}

    ingested = 0
    async for job in adapter.search(query="", location=None, page=1, page_size=50, filters={}):
        job.tenant_id = tenant_id
        was_new = await upsert_job(job, db, typesense_client, chroma_client)
        if was_new:
            ingested += 1
            await broadcast_new_job(job)

    await log_ingestion_run(source_name, ingested, db, tenant_id)
    return {"source": source_name, "new_jobs": ingested}


async def ingest_greenhouse(ctx: dict) -> dict[str, object]:
    """Cron wrapper for greenhouse source."""

    return await ingest_source(ctx, "greenhouse")


async def ingest_lever(ctx: dict) -> dict[str, object]:
    """Cron wrapper for lever source."""

    return await ingest_source(ctx, "lever")


async def ingest_remoteok(ctx: dict) -> dict[str, object]:
    """Cron wrapper for remoteok source."""

    return await ingest_source(ctx, "remoteok")


async def ingest_adzuna(ctx: dict) -> dict[str, object]:
    """Cron wrapper for adzuna source."""

    return await ingest_source(ctx, "adzuna")


async def ingest_arbeitnow(ctx: dict) -> dict[str, object]:
    """Cron wrapper for arbeitnow source."""

    return await ingest_source(ctx, "arbeitnow")


async def ingest_the_muse(ctx: dict) -> dict[str, object]:
    """Cron wrapper for the muse source."""

    return await ingest_source(ctx, "the_muse")


async def ingest_usajobs(ctx: dict) -> dict[str, object]:
    """Cron wrapper for usajobs source."""

    return await ingest_source(ctx, "usajobs")


async def ingest_jobspy(ctx: dict) -> dict[str, object]:
    """Cron wrapper for jobspy source."""

    return await ingest_source(ctx, "jobspy")


async def _get_default_tenant_id(db: AsyncSession) -> UUID | None:
    """Resolve one active tenant as ingestion target."""

    result = await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True)).limit(1))
    return result.scalar_one_or_none()


async def startup(ctx: dict) -> None:
    """Initialize worker dependencies."""

    ctx["db"] = AsyncSessionFactory()
    ctx["typesense"] = get_typesense_client()
    await ensure_jobs_collection(ctx["typesense"])
    ctx["chroma"] = chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT)
    tenant_id = await _get_default_tenant_id(ctx["db"])
    ctx["tenant_id"] = tenant_id


async def shutdown(ctx: dict) -> None:
    """Release worker dependencies."""

    db: AsyncSession = ctx["db"]
    await db.close()


class WorkerSettings:
    """ARQ worker settings."""

    functions = [
        ingest_source,
        ingest_greenhouse,
        ingest_lever,
        ingest_remoteok,
        ingest_adzuna,
        ingest_arbeitnow,
        ingest_the_muse,
        ingest_usajobs,
        ingest_jobspy,
    ]
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        cron(ingest_greenhouse, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(ingest_lever, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(ingest_remoteok, minute={0, 10, 20, 30, 40, 50}),
        cron(ingest_adzuna, minute={0, 30}),
        cron(ingest_arbeitnow, minute={0, 30}),
        cron(ingest_the_muse, minute={0}),
        cron(ingest_usajobs, minute={0}),
        cron(ingest_jobspy, minute={0, 20, 40}),
    ]
