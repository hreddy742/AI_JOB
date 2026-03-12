"""Admin routes for ingestion and supervisor controls."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.redis import get_redis
from core.security import TokenPayload
from db.models.dedup_log import DedupLog
from db.models.job import Job
from db.models.job_requirement import JobRequirement
from db.models.supervisor_log import SupervisorLog
from db.models.tenant import Tenant
from services.search_service import get_typesense_client
from services.job_coverage.metrics import to_dashboard_payload
from services.feature_flags import get_tenant_rerank_state, set_tenant_rerank_override

from services.ingestion_service import adapter_factories, expire_old_jobs, run_default_ingestion_cycle, run_ingestion_for_sources
from services.job_service import backfill_job_categories

router = APIRouter(prefix="/admin", tags=["admin"])
_KNOWN_LLM_FLOWS = [
    "resume_tailoring_graph",
    "cover_letter_generation",
    "screening_answer_draft",
    "resume_review",
    "resume_parser_json_extract",
    "resume_bullet_improve",
    "resume_builder_bullet_enhance",
    "resume_builder_summary",
    "copilot_chat_turn",
    "copilot_jd_analysis",
    "copilot_technical_questions",
    "outreach_compliance_review",
    "referral_company_analyzer",
]


class RerankConfigUpdate(BaseModel):
    enabled: bool | None = None


def _query_expansions_path() -> Path:
    """Resolve canonical query expansion YAML path."""

    root_path = Path(__file__).resolve().parents[3] / "config" / "query_expansions.yml"
    app_path = Path(__file__).resolve().parents[1] / "config" / "query_expansions.yml"
    if root_path.exists() or not app_path.exists():
        return root_path
    return app_path


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


@router.get("/metrics/ingestion")
async def ingestion_metrics(
    days: int = 7,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return per-source ingestion metrics from Redis for the last N days."""

    _admin_guard(token)
    days = max(1, min(days, 30))
    redis = get_redis()
    today = datetime.now(UTC).date()
    sources = sorted(adapter_factories().keys())
    output: dict[str, dict[str, dict[str, int | str]]] = {}

    for source in sources:
        per_day: dict[str, dict[str, str]] = {}
        for offset in range(days):
            day = (today - timedelta(days=offset)).isoformat()
            key = f"metrics:ingestion:{source}:{day}"
            payload = await redis.hgetall(key)
            if payload:
                per_day[day] = {
                    "inserted": int(payload.get("inserted", "0")),
                    "updated": int(payload.get("updated", "0")),
                    "skipped": int(payload.get("skipped", "0")),
                    "errors": int(payload.get("errors", "0")),
                    "last_run": str(payload.get("last_run", "")),
                }
        if per_day:
            output[source] = per_day
    return output


@router.get("/metrics/coverage/queries")
async def coverage_dashboard_queries(
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return SQL query templates for coverage dashboards."""

    _admin_guard(token)
    return to_dashboard_payload()


@router.get("/coverage/dashboard")
async def coverage_dashboard(
    days: int = 7,
    stale_after_minutes: int = 180,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregated ingestion and coverage dashboard metrics for admin visibility."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    days = max(1, min(days, 30))
    stale_after_minutes = max(15, min(stale_after_minutes, 1440))
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    sources = sorted(adapter_factories().keys())

    active_rows = (
        await db.execute(
            select(Job.source, func.count())
            .where(Job.tenant_id == tenant_id, Job.is_active.is_(True))
            .group_by(Job.source)
        )
    ).all()
    active_by_source = {str(source): int(count) for source, count in active_rows}

    ingested_rows = (
        await db.execute(
            select(Job.source, func.count())
            .where(Job.tenant_id == tenant_id, Job.ingested_at >= since)
            .group_by(Job.source)
        )
    ).all()
    ingested_by_source = {str(source): int(count) for source, count in ingested_rows}

    unsynced_jobs = int(
        (
            await db.execute(
                select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id, Job.typesense_synced.is_(False))
            )
        ).scalar_one()
    )
    requirements_backlog = int(
        (
            await db.execute(
                select(func.count())
                .select_from(JobRequirement)
                .where(
                    JobRequirement.tenant_id == tenant_id,
                    JobRequirement.status.in_(["queued", "processing"]),
                )
            )
        ).scalar_one()
    )

    log_rows = (
        await db.execute(
            select(SupervisorLog.created_at, SupervisorLog.payload)
            .where(
                SupervisorLog.tenant_id == tenant_id,
                SupervisorLog.event_type == "ingestion_run",
                SupervisorLog.created_at >= since,
            )
            .order_by(desc(SupervisorLog.created_at))
            .limit(1000)
        )
    ).all()
    logs_by_source: dict[str, dict[str, datetime | int | None]] = {}
    for created_at, payload in log_rows:
        source = str((payload or {}).get("source") or "")
        if not source:
            continue
        info = logs_by_source.setdefault(source, {"runs": 0, "new_jobs": 0, "errors": 0, "last_run_at": None})
        info["runs"] = int(info["runs"] or 0) + 1
        info["new_jobs"] = int(info["new_jobs"] or 0) + int((payload or {}).get("new_jobs") or 0)
        info["errors"] = int(info["errors"] or 0) + int((payload or {}).get("errors") or 0)
        if info["last_run_at"] is None:
            info["last_run_at"] = created_at

    redis = get_redis()
    source_rows: list[dict[str, object]] = []
    failed_runs_window = 0

    for source in sources:
        coverage_totals = {
            "jobs_ingested": 0,
            "jobs_failed": 0,
            "freshness_latency_seconds": None,
        }
        ingestion_totals = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for offset in range(days):
            day = (now.date() - timedelta(days=offset)).isoformat()
            coverage_key = f"metrics:coverage:{source}:{day}"
            ingestion_key = f"metrics:ingestion:{source}:{day}"
            coverage_payload = await redis.hgetall(coverage_key)
            ingestion_payload = await redis.hgetall(ingestion_key)

            if coverage_payload:
                coverage_totals["jobs_ingested"] += int(coverage_payload.get("jobs_ingested_per_source", "0"))
                coverage_totals["jobs_failed"] += int(coverage_payload.get("jobs_failed_per_source", "0"))
                if coverage_totals["freshness_latency_seconds"] is None:
                    latency_raw = coverage_payload.get("freshness_latency_seconds")
                    if latency_raw is not None:
                        coverage_totals["freshness_latency_seconds"] = float(latency_raw)
            if ingestion_payload:
                ingestion_totals["inserted"] += int(ingestion_payload.get("inserted", "0"))
                ingestion_totals["updated"] += int(ingestion_payload.get("updated", "0"))
                ingestion_totals["skipped"] += int(ingestion_payload.get("skipped", "0"))
                ingestion_totals["errors"] += int(ingestion_payload.get("errors", "0"))

        log_info = logs_by_source.get(source, {"runs": 0, "new_jobs": 0, "errors": 0, "last_run_at": None})
        last_run_at = log_info.get("last_run_at")
        minutes_since_last_run = (
            int((now - last_run_at).total_seconds() // 60) if isinstance(last_run_at, datetime) else None
        )
        stale = minutes_since_last_run is None or minutes_since_last_run > stale_after_minutes
        failed_runs_window += int(log_info.get("errors") or 0)

        source_rows.append(
            {
                "source": source,
                "active_jobs": active_by_source.get(source, 0),
                "ingested_jobs_window": ingested_by_source.get(source, 0),
                "runs_window": int(log_info.get("runs") or 0),
                "new_jobs_window": int(log_info.get("new_jobs") or 0),
                "errors_window": int(log_info.get("errors") or 0),
                "last_run_at": last_run_at.isoformat() if isinstance(last_run_at, datetime) else None,
                "minutes_since_last_run": minutes_since_last_run,
                "stale": stale,
                "coverage_metrics": coverage_totals,
                "ingestion_metrics": ingestion_totals,
            }
        )

    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "stale_after_minutes": stale_after_minutes,
        "summary": {
            "active_jobs_total": sum(active_by_source.values()),
            "ingested_jobs_window_total": sum(ingested_by_source.values()),
            "typesense_backlog": unsynced_jobs,
            "requirements_backlog": requirements_backlog,
            "sources_total": len(sources),
            "stale_sources": sum(1 for row in source_rows if bool(row["stale"])),
            "failed_runs_window": failed_runs_window,
        },
        "sources": source_rows,
    }


@router.get("/requirements/status")
async def requirements_status(
    stale_minutes: int | None = None,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return queue status breakdown for job requirements processing."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    stale_cutoff_minutes = int(stale_minutes or settings.JOB_REQUIREMENTS_STALE_MINUTES)
    stale_cutoff_minutes = max(1, min(stale_cutoff_minutes, 1440))
    stale_before = datetime.now(UTC) - timedelta(minutes=stale_cutoff_minutes)

    rows = (
        await db.execute(
            select(JobRequirement.status, func.count())
            .where(JobRequirement.tenant_id == tenant_id)
            .group_by(JobRequirement.status)
        )
    ).all()
    counts = {str(status): int(count) for status, count in rows}

    stale_processing = int(
        (
            await db.execute(
                select(func.count())
                .select_from(JobRequirement)
                .where(
                    JobRequirement.tenant_id == tenant_id,
                    JobRequirement.status == "processing",
                    JobRequirement.updated_at < stale_before,
                )
            )
        ).scalar_one()
    )

    oldest_queued_at = (
        await db.execute(
            select(func.min(JobRequirement.updated_at)).where(
                JobRequirement.tenant_id == tenant_id,
                JobRequirement.status == "queued",
            )
        )
    ).scalar_one()

    now = datetime.now(UTC)
    oldest_age_minutes = (
        int((now - oldest_queued_at).total_seconds() // 60) if isinstance(oldest_queued_at, datetime) else None
    )
    return {
        "generated_at": now.isoformat(),
        "counts": counts,
        "total": int(sum(counts.values())),
        "stale_processing": stale_processing,
        "stale_processing_cutoff_minutes": stale_cutoff_minutes,
        "oldest_queued_at": oldest_queued_at.isoformat() if isinstance(oldest_queued_at, datetime) else None,
        "oldest_queued_age_minutes": oldest_age_minutes,
    }


@router.get("/alerts/status")
async def alerts_status(
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return notification stream visibility for ready/pending/dlq queues."""

    _admin_guard(token)
    redis = get_redis()
    now = datetime.now(UTC)
    stream_ready = "stream:alerts:ready"
    stream_failed = "stream:alerts:failed"
    group = "alerts-delivery"

    try:
        ready_len = int(await redis.xlen(stream_ready) or 0)
    except Exception:
        ready_len = 0
    try:
        failed_len = int(await redis.xlen(stream_failed) or 0)
    except Exception:
        failed_len = 0
    try:
        pending_info = await redis.xpending(stream_ready, group)
        pending = int((pending_info or {}).get("pending", 0) or 0) if isinstance(pending_info, dict) else 0
    except Exception:
        pending = 0

    return {
        "generated_at": now.isoformat(),
        "stream": {
            "ready": stream_ready,
            "failed": stream_failed,
            "group": group,
        },
        "counts": {
            "ready": ready_len,
            "pending": pending,
            "failed_dlq": failed_len,
        },
    }


@router.get("/llm/usage")
async def llm_usage(
    days: int = 7,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return LLM usage/latency counters aggregated from Redis telemetry keys."""

    _admin_guard(token)
    days = max(1, min(days, 14))
    now = datetime.now(UTC)
    redis = get_redis()

    day_rows: dict[str, dict[str, float | int | str]] = {}
    flow_totals: dict[str, dict[str, float | int]] = {}
    summary = {
        "calls": 0,
        "success": 0,
        "failed": 0,
        "prompt_chars": 0,
        "output_chars": 0,
        "prompt_tokens_est": 0,
        "output_tokens_est": 0,
        "latency_ms_total": 0.0,
    }

    for offset in range(days):
        day = (now.date() - timedelta(days=offset)).isoformat()
        day_payload = await redis.hgetall(f"metrics:llm:day:{day}")
        if day_payload:
            parsed_day = {
                "calls": int(float(day_payload.get("calls", "0") or 0)),
                "success": int(float(day_payload.get("success", "0") or 0)),
                "failed": int(float(day_payload.get("failed", "0") or 0)),
                "prompt_chars": int(float(day_payload.get("prompt_chars", "0") or 0)),
                "output_chars": int(float(day_payload.get("output_chars", "0") or 0)),
                "prompt_tokens_est": int(float(day_payload.get("prompt_tokens_est", "0") or 0)),
                "output_tokens_est": int(float(day_payload.get("output_tokens_est", "0") or 0)),
                "latency_ms_total": float(day_payload.get("latency_ms_total", "0") or 0.0),
                "last_updated": str(day_payload.get("last_updated", "")),
            }
            day_rows[day] = parsed_day
            summary["calls"] += parsed_day["calls"]
            summary["success"] += parsed_day["success"]
            summary["failed"] += parsed_day["failed"]
            summary["prompt_chars"] += parsed_day["prompt_chars"]
            summary["output_chars"] += parsed_day["output_chars"]
            summary["prompt_tokens_est"] += parsed_day["prompt_tokens_est"]
            summary["output_tokens_est"] += parsed_day["output_tokens_est"]
            summary["latency_ms_total"] += parsed_day["latency_ms_total"]

        for flow in _KNOWN_LLM_FLOWS:
            payload = await redis.hgetall(f"metrics:llm:flow:{flow}:{day}")
            if not payload:
                continue
            row = flow_totals.setdefault(
                flow,
                {"calls": 0, "success": 0, "failed": 0, "prompt_tokens_est": 0, "output_tokens_est": 0, "latency_ms_total": 0.0},
            )
            row["calls"] += int(float(payload.get("calls", "0") or 0))
            row["success"] += int(float(payload.get("success", "0") or 0))
            row["failed"] += int(float(payload.get("failed", "0") or 0))
            row["prompt_tokens_est"] += int(float(payload.get("prompt_tokens_est", "0") or 0))
            row["output_tokens_est"] += int(float(payload.get("output_tokens_est", "0") or 0))
            row["latency_ms_total"] += float(payload.get("latency_ms_total", "0") or 0.0)

    calls = int(summary["calls"])
    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "summary": {
            **summary,
            "average_latency_ms": round(summary["latency_ms_total"] / calls, 3) if calls > 0 else 0.0,
            "success_rate": round(summary["success"] / calls, 4) if calls > 0 else 0.0,
        },
        "days": day_rows,
        "flows": flow_totals,
    }


@router.get("/ranking/rerank-status")
async def rerank_status(
    days: int = 7,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return tenant-scoped rerank observability rollups from Redis."""

    _admin_guard(token)
    tenant_id = token.tenant_id
    days = max(1, min(days, 30))
    now = datetime.now(UTC)
    redis = get_redis()

    per_day: dict[str, dict[str, float | int | str | None]] = {}
    totals: dict[str, float] = {
        "attempts": 0.0,
        "applied": 0.0,
        "timeout": 0.0,
        "failed": 0.0,
        "skipped_disabled": 0.0,
        "skipped_min_candidates": 0.0,
        "candidates_total": 0.0,
        "latency_ms_total": 0.0,
    }
    last_updated: str | None = None

    for offset in range(days):
        day = (now.date() - timedelta(days=offset)).isoformat()
        key = f"metrics:rerank:{tenant_id}:{day}"
        row = await redis.hgetall(key)
        if not row:
            continue
        payload = {
            "attempts": int(float(row.get("attempts", "0") or 0)),
            "applied": int(float(row.get("applied", "0") or 0)),
            "timeout": int(float(row.get("timeout", "0") or 0)),
            "failed": int(float(row.get("failed", "0") or 0)),
            "skipped_disabled": int(float(row.get("skipped_disabled", "0") or 0)),
            "skipped_min_candidates": int(float(row.get("skipped_min_candidates", "0") or 0)),
            "candidates_total": int(float(row.get("candidates_total", "0") or 0)),
            "latency_ms_total": float(row.get("latency_ms_total", "0") or 0.0),
            "last_outcome": row.get("last_outcome"),
            "last_updated": row.get("last_updated"),
        }
        per_day[day] = payload
        for metric_name in totals.keys():
            totals[metric_name] += float(payload.get(metric_name, 0) or 0.0)
        if isinstance(payload.get("last_updated"), str):
            if last_updated is None or payload["last_updated"] > last_updated:
                last_updated = payload["last_updated"]

    attempts = int(totals["attempts"])
    average_latency_ms = (totals["latency_ms_total"] / totals["applied"]) if totals["applied"] > 0 else 0.0
    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "summary": {
            "attempts": attempts,
            "applied": int(totals["applied"]),
            "timeout": int(totals["timeout"]),
            "failed": int(totals["failed"]),
            "skipped_disabled": int(totals["skipped_disabled"]),
            "skipped_min_candidates": int(totals["skipped_min_candidates"]),
            "candidates_total": int(totals["candidates_total"]),
            "latency_ms_total": round(totals["latency_ms_total"], 3),
            "average_latency_ms": round(average_latency_ms, 3),
            "apply_rate": round((totals["applied"] / attempts), 4) if attempts > 0 else 0.0,
            "timeout_rate": round((totals["timeout"] / attempts), 4) if attempts > 0 else 0.0,
            "last_updated": last_updated,
        },
        "days": per_day,
    }


@router.get("/ranking/rerank-readiness")
async def rerank_readiness(
    days: int = 7,
    min_attempts: int = 100,
    max_timeout_rate: float = 0.05,
    max_failure_rate: float = 0.02,
    max_average_latency_ms: float = 800.0,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Evaluate whether reranking is operationally ready for enablement."""

    _admin_guard(token)
    # Reuse status rollup to keep one source of truth.
    status_payload = await rerank_status(days=days, token=token)
    summary = status_payload.get("summary", {})

    attempts = int(summary.get("attempts", 0) or 0)
    applied = int(summary.get("applied", 0) or 0)
    timeout_rate = float(summary.get("timeout_rate", 0.0) or 0.0)
    failure_rate = (float(summary.get("failed", 0) or 0.0) / attempts) if attempts > 0 else 0.0
    avg_latency = float(summary.get("average_latency_ms", 0.0) or 0.0)

    checks = {
        "min_attempts": attempts >= int(min_attempts),
        "has_applied": applied > 0,
        "timeout_rate": timeout_rate <= float(max_timeout_rate),
        "failure_rate": failure_rate <= float(max_failure_rate),
        "average_latency_ms": avg_latency <= float(max_average_latency_ms),
    }
    ready = all(checks.values())

    reasons: list[str] = []
    if not checks["min_attempts"]:
        reasons.append(f"insufficient_attempts:{attempts}<{int(min_attempts)}")
    if not checks["has_applied"]:
        reasons.append("no_applied_runs")
    if not checks["timeout_rate"]:
        reasons.append(f"timeout_rate_high:{timeout_rate:.4f}>{float(max_timeout_rate):.4f}")
    if not checks["failure_rate"]:
        reasons.append(f"failure_rate_high:{failure_rate:.4f}>{float(max_failure_rate):.4f}")
    if not checks["average_latency_ms"]:
        reasons.append(f"latency_high:{avg_latency:.3f}>{float(max_average_latency_ms):.3f}")

    return {
        "generated_at": status_payload.get("generated_at"),
        "window_days": int(status_payload.get("window_days", days)),
        "ready_to_enable_reranking": ready,
        "checks": checks,
        "thresholds": {
            "min_attempts": int(min_attempts),
            "max_timeout_rate": float(max_timeout_rate),
            "max_failure_rate": float(max_failure_rate),
            "max_average_latency_ms": float(max_average_latency_ms),
        },
        "summary": summary,
        "reasons": reasons,
    }


@router.get("/ranking/rerank-config")
async def rerank_config(
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return tenant-scoped reranking feature-flag state."""

    _admin_guard(token)
    state = await get_tenant_rerank_state(token.tenant_id)
    return state


@router.put("/ranking/rerank-config")
async def update_rerank_config(
    payload: RerankConfigUpdate,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Set/clear tenant reranking override (None clears override)."""

    _admin_guard(token)
    state = await set_tenant_rerank_override(token.tenant_id, payload.enabled)
    return state


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
    normalized_source = source_name.strip()
    if normalized_source not in adapter_factories():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown source: {normalized_source}")
    result = await run_ingestion_for_sources(db, tenant_id, [normalized_source], min_age_hours=0)
    return {
        "source": normalized_source,
        "results": result,
        "tenant_id": str(tenant_id),
    }


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
        "supported_sources": sorted(adapter_factories().keys()),
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
    unknown = [name for name in names if name not in adapter_factories()]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown sources: {', '.join(unknown)}")
    result = await run_ingestion_for_sources(db, tenant_id, names, min_age_hours=min_age_hours)
    return {"results": result}


@router.get("/query-expansions")
async def get_query_expansions(
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Return current query expansion map."""

    _admin_guard(token)
    target = _query_expansions_path()
    if not target.exists():
        return {"expansions": {}}
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        data = {}
    return {"expansions": data}


@router.put("/query-expansions")
async def update_query_expansions(
    payload: dict,
    token: TokenPayload = Depends(get_current_token),
) -> dict:
    """Update query expansion YAML content."""

    _admin_guard(token)
    expansions = payload.get("expansions", payload)
    if not isinstance(expansions, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expansions must be an object")
    target = _query_expansions_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(expansions, sort_keys=True), encoding="utf-8")
    return {"status": "updated", "count": len(expansions)}


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


@router.get("/dedup/stats")
async def dedup_stats(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return dedup decision breakdown for the last 24 hours."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    since = datetime.now(UTC) - timedelta(hours=24)
    rows = (
        await db.execute(
            select(DedupLog.method, func.count())
            .join(Job, Job.id == DedupLog.job_id)
            .where(
                DedupLog.created_at >= since,
                Job.tenant_id == tenant_id,
            )
            .group_by(DedupLog.method)
        )
    ).all()
    breakdown = {str(method or "unknown"): int(count) for method, count in rows}
    return {"since": since.isoformat(), "breakdown": breakdown}


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
    for source in sorted(adapter_factories().keys()):
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


@router.post("/backfill-categories")
async def backfill_categories(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-classify category/subcategory for all jobs that still have defaults."""

    _admin_guard(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    typesense = get_typesense_client()
    result = await backfill_job_categories(db, tenant_id, typesense)
    return {"status": "ok", **result}


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
