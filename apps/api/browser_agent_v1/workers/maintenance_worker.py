"""Maintenance worker for Browser Agent V1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

try:
    from arq import cron
    from arq.connections import RedisSettings
except ModuleNotFoundError:  # pragma: no cover - test/import fallback
    def cron(*_args, **_kwargs):  # type: ignore[override]
        return None

    class RedisSettings:  # type: ignore[override]
        @classmethod
        def from_dsn(cls, _dsn: str):
            return cls()
from sqlalchemy import select

from core.arq_queues import QUEUE_BROWSER_AGENT_V1_MAINT
from core.config import settings
from core.worker_metrics import start_worker_metrics_server
from db.models.browser_agent_artifact import BrowserAgentArtifact
from db.models.browser_agent_run import BrowserAgentRun
from db.session import AsyncSessionFactory
from browser_agent_v1.storage import put_artifact_bytes
from sqlalchemy import text


async def cleanup_stale_browser_agent_runs(ctx: dict[str, Any]) -> dict[str, Any]:
    """Mark long-running stale runs as failed for operator visibility."""

    stale_cutoff = datetime.now(UTC) - timedelta(minutes=max(5, int(settings.BROWSER_AGENT_V1_STALE_RUN_MINUTES)))
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(BrowserAgentRun).where(
                BrowserAgentRun.status == "running",
                BrowserAgentRun.last_heartbeat_at.is_not(None),
                BrowserAgentRun.last_heartbeat_at < stale_cutoff,
            )
        )
        runs = list(result.scalars().all())
        for run in runs:
            run.status = "failed"
            run.error_code = "stale_run"
            run.error_detail = "Browser Agent V1 stale-run maintenance marked this run failed."
            run.completed_at = datetime.now(UTC)
        if runs:
            await db.commit()
    return {"stale_runs_marked_failed": len(runs)}


async def backfill_browser_agent_artifacts(ctx: dict[str, Any], *, limit: int = 100) -> dict[str, Any]:
    """Move legacy inline Browser Agent artifacts into object storage."""

    migrated = 0
    scanned = 0
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                select(BrowserAgentArtifact)
                .where(
                    BrowserAgentArtifact.storage_path.is_(None),
                    BrowserAgentArtifact.inline_text.is_not(None),
                )
                .order_by(BrowserAgentArtifact.created_at.asc())
                .limit(max(1, int(limit))),
            )
        ).scalars().all()
        for artifact in rows:
            scanned += 1
            try:
                import base64

                payload = base64.b64decode(str(artifact.inline_text or "").encode("ascii"))
                storage_path, metadata = put_artifact_bytes(
                    run_id=artifact.run_id,
                    artifact_type=artifact.artifact_type,
                    content_type=artifact.content_type or "application/octet-stream",
                    payload=payload,
                )
                artifact.storage_path = storage_path
                artifact.metadata_json = {**(artifact.metadata_json or {}), **metadata, "migrated_from_inline": True}
                migrated += 1
            except Exception:
                continue
        if rows:
            await db.commit()
    return {"artifacts_scanned": scanned, "artifacts_migrated": migrated}


async def refresh_analytics_materialized_views(ctx: dict[str, Any]) -> dict[str, bool]:
    """Refresh analytics materialized views on a maintenance schedule."""

    if not settings.BROWSER_AGENT_V1_REFRESH_ANALYTICS_MARTS:
        return {"refreshed": False}
    async with AsyncSessionFactory() as db:
        await db.execute(text("REFRESH MATERIALIZED VIEW mv_user_application_funnel"))
        await db.execute(text("REFRESH MATERIALIZED VIEW mv_user_referral_metrics"))
        await db.commit()
    return {"refreshed": True}


async def startup(ctx: dict[str, Any]) -> None:
    """Expose Prometheus metrics for Browser Agent maintenance jobs."""

    ctx["metrics_port"] = start_worker_metrics_server(int(settings.BROWSER_AGENT_V1_MAINT_WORKER_METRICS_PORT))


class WorkerSettings:
    """ARQ worker settings for Browser Agent V1 maintenance."""

    functions = [cleanup_stale_browser_agent_runs, backfill_browser_agent_artifacts, refresh_analytics_materialized_views]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    queue_name = QUEUE_BROWSER_AGENT_V1_MAINT
    cron_jobs = [
        cron(refresh_analytics_materialized_views, minute=set(range(0, 60, max(1, int(settings.BROWSER_AGENT_V1_ANALYTICS_REFRESH_MINUTES))))),
    ]
