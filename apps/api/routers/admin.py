"""Admin routes for ingestion and supervisor controls."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.job import Job
from db.models.supervisor_log import SupervisorLog
from db.models.tenant import Tenant
from services.search_service import get_typesense_client
import chromadb

from workers.ingestion_worker import ingest_source
from services.ingestion_service import ADAPTERS, expire_old_jobs, run_default_ingestion_cycle, run_ingestion_for_sources

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_guard(token: TokenPayload) -> None:
    """Require admin role for admin routes."""

    if token.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


@router.get("/ingestion/status")
async def ingestion_status(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return latest ingestion runs from supervisor logs."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(SupervisorLog)
        .where(SupervisorLog.event_type == "ingestion_run", SupervisorLog.tenant_id == tenant_id)
        .order_by(desc(SupervisorLog.created_at))
        .limit(20)
    )
    logs = result.scalars().all()
    return {
        "runs": [
            {
                "id": str(log.id),
                "created_at": log.created_at.isoformat(),
                "payload": log.payload,
            }
            for log in logs
        ]
    }


@router.post("/ingestion/trigger")
async def ingestion_trigger(
    source_name: str,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger on-demand ingestion for a source."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    ctx = {
        "db": db,
        "tenant_id": tenant_id,
        "typesense": get_typesense_client(),
        "chroma": chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT),
    }
    result = await ingest_source(ctx, source_name)
    return result


@router.post("/ingestion/trigger-all")
async def ingestion_trigger_all(
    min_age_hours: int = 0,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger ingestion across default sources in one call."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    if min_age_hours < 0 or min_age_hours > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_age_hours must be between 0 and 120")

    if min_age_hours == 0:
        result = await run_default_ingestion_cycle(db, tenant_id)
    else:
        from services.ingestion_service import DEFAULT_INGESTION_SOURCES

        result = await run_ingestion_for_sources(db, tenant_id, list(DEFAULT_INGESTION_SOURCES), min_age_hours=min_age_hours)
        result["expired"] = await expire_old_jobs(db, tenant_id, days=settings.JOB_RETENTION_DAYS)
    return {
        "sources": list(result.keys()),
        "results": result,
        "supported_sources": sorted(ADAPTERS.keys()),
    }


@router.post("/ingestion/trigger-batch")
async def ingestion_trigger_batch(
    source_names: str,
    min_age_hours: int = 0,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger ingestion for a comma-separated source list."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    names = [name.strip() for name in source_names.split(",") if name.strip()]
    result = await run_ingestion_for_sources(db, tenant_id, names, min_age_hours=min_age_hours)
    return {"results": result}


@router.get("/supervisor/logs")
async def supervisor_logs(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List supervisor logs for tenant."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(SupervisorLog).where(SupervisorLog.tenant_id == tenant_id).order_by(desc(SupervisorLog.created_at)).limit(100)
    )
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": str(item.id),
                "event_type": item.event_type,
                "severity": str(item.severity.value if hasattr(item.severity, "value") else item.severity),
                "payload": item.payload,
                "resolved": item.resolved,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }


@router.patch("/supervisor/logs/{id}")
async def resolve_supervisor_log(
    id: UUID,
    resolved: bool = True,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve/unresolve a supervisor log."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(SupervisorLog).where(SupervisorLog.id == id, SupervisorLog.tenant_id == tenant_id))
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")

    log.resolved = resolved
    await db.commit()
    return {"id": str(id), "resolved": resolved}


@router.get("/typesense/status")
async def typesense_status(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return index document count and sync lag."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    synced_result = await db.execute(
        select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id, Job.typesense_synced.is_(True))
    )
    unsynced_result = await db.execute(
        select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id, Job.typesense_synced.is_(False))
    )
    typesense = get_typesense_client()
    docs_count = 0
    try:
        collection = typesense.collections[settings.TYPESENSE_JOBS_COLLECTION].retrieve()
        docs_count = int(collection.get("num_documents", 0))
    except Exception:
        docs_count = 0

    return {
        "typesense_documents": docs_count,
        "synced_jobs": int(synced_result.scalar_one()),
        "sync_lag": int(unsynced_result.scalar_one()),
    }


@router.get("/ingestion/health")
async def ingestion_health(
    stale_after_minutes: int = 180,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-source ingestion health and coverage diagnostics."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)

    logs = (
        await db.execute(
            select(SupervisorLog)
            .where(
                SupervisorLog.tenant_id == tenant_id,
                SupervisorLog.event_type == "ingestion_run",
            )
            .order_by(desc(SupervisorLog.created_at))
            .limit(500)
        )
    ).scalars().all()

    counts = (
        await db.execute(
            select(Job.source, func.count())
            .where(Job.tenant_id == tenant_id, Job.is_active.is_(True))
            .group_by(Job.source)
        )
    ).all()
    count_by_source = {str(source): int(total) for source, total in counts}

    latest_by_source: dict[str, SupervisorLog] = {}
    inserted_24h_by_source: dict[str, int] = {}
    runs_24h_by_source: dict[str, int] = {}

    for log in logs:
        source = str((log.payload or {}).get("source") or "")
        if not source:
            continue
        if source not in latest_by_source:
            latest_by_source[source] = log
        if log.created_at >= day_ago:
            runs_24h_by_source[source] = runs_24h_by_source.get(source, 0) + 1
            inserted_24h_by_source[source] = inserted_24h_by_source.get(source, 0) + int(
                (log.payload or {}).get("new_jobs") or 0
            )

    items = []
    for source in sorted(ADAPTERS.keys()):
        latest = latest_by_source.get(source)
        last_run_at = latest.created_at if latest else None
        minutes_since_last = int((now - last_run_at).total_seconds() // 60) if last_run_at else None
        items.append(
            {
                "source": source,
                "active_jobs": count_by_source.get(source, 0),
                "runs_24h": runs_24h_by_source.get(source, 0),
                "new_jobs_24h": inserted_24h_by_source.get(source, 0),
                "last_run_at": last_run_at.isoformat() if last_run_at else None,
                "minutes_since_last_run": minutes_since_last,
                "stale": minutes_since_last is None or minutes_since_last > stale_after_minutes,
            }
        )

    return {
        "generated_at": now.isoformat(),
        "stale_after_minutes": stale_after_minutes,
        "sources": items,
    }


@router.get("/tenants")
async def list_tenants(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List tenants (admin only)."""

    _admin_guard(token)
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    return {
        "items": [
            {
                "id": str(t.id),
                "name": t.name,
                "plan": str(t.plan.value if hasattr(t.plan, "value") else t.plan),
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat(),
            }
            for t in tenants
        ]
    }
