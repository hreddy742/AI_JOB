"""Supervisor agent for platform health checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.chat_session import ChatSession
from db.models.job import Job
from db.models.referral import ReferralSuggestion
from db.models.supervisor_log import SupervisorLog


class SupervisorAgent:
    """Platform supervisor that runs periodic health checks."""

    SEVERITY_ACTIONS: dict[str, list[str]] = {
        "info": ["log"],
        "medium": ["log", "in_app_notify"],
        "high": ["log", "in_app_notify", "email_notify"],
        "critical": ["log", "in_app_notify", "email_notify", "webhook", "halt_pipeline"],
    }

    async def run_once(self, ctx: dict[str, Any]) -> None:
        """Run all supervisor checks one cycle."""

        await self._check_ingestion_health(ctx)
        await self._check_tailoring_violations(ctx)
        await self._check_automation_errors(ctx)
        await self._check_outreach_risks(ctx)
        await self._check_quota_usage(ctx)
        await self._check_typesense_sync_lag(ctx)
        await self._check_referral_engine_health(ctx)
        await self._check_copilot_error_rate(ctx)

    async def _emit(self, db: AsyncSession, tenant_id: UUID, event_type: str, severity: str, payload: dict[str, Any]) -> None:
        """Persist supervisor log entry."""

        entry = SupervisorLog(
            tenant_id=tenant_id,
            event_type=event_type,
            severity=severity,
            payload=payload,
            resolved=False,
        )
        db.add(entry)
        await db.commit()

    async def _get_default_tenant(self, db: AsyncSession) -> UUID | None:
        """Infer tenant id from recent logs/jobs."""

        recent = await db.execute(select(SupervisorLog.tenant_id).order_by(desc(SupervisorLog.created_at)).limit(1))
        tenant = recent.scalar_one_or_none()
        if tenant:
            return tenant
        job_tenant = await db.execute(select(Job.tenant_id).limit(1))
        return job_tenant.scalar_one_or_none()

    async def _check_ingestion_health(self, ctx: dict[str, Any]) -> None:
        """Basic ingestion heartbeat check."""

        db: AsyncSession = ctx["db"]
        tenant = await self._get_default_tenant(db)
        if tenant is None:
            return
        window = datetime.now(UTC) - timedelta(hours=2)
        count_result = await db.execute(
            select(func.count()).select_from(SupervisorLog).where(
                and_(
                    SupervisorLog.event_type == "ingestion_run",
                    SupervisorLog.created_at >= window,
                )
            )
        )
        count = int(count_result.scalar_one())
        if count == 0:
            await self._emit(db, tenant, "ingestion_health", "medium", {"reason": "No ingestion run in last 2h"})

    async def _check_tailoring_violations(self, ctx: dict[str, Any]) -> None:
        """Placeholder tailoring violations check."""

        return

    async def _check_automation_errors(self, ctx: dict[str, Any]) -> None:
        """Placeholder automation errors check."""

        return

    async def _check_outreach_risks(self, ctx: dict[str, Any]) -> None:
        """Placeholder outreach risk check."""

        return

    async def _check_quota_usage(self, ctx: dict[str, Any]) -> None:
        """Placeholder quota usage check."""

        return

    async def _check_typesense_sync_lag(self, ctx: dict[str, Any]) -> None:
        """Alert if Typesense sync lag exceeds threshold."""

        db: AsyncSession = ctx["db"]
        tenant = await self._get_default_tenant(db)
        if tenant is None:
            return

        cutoff = datetime.now(UTC) - timedelta(minutes=10)
        count_result = await db.execute(
            select(func.count()).select_from(Job).where(
                and_(
                    Job.typesense_synced.is_(False),
                    Job.ingested_at < cutoff,
                )
            )
        )
        lag_count = int(count_result.scalar_one())
        if lag_count > 50:
            await self._emit(
                db,
                tenant,
                "typesense_sync_lag",
                "high",
                {"count": lag_count, "threshold": 50, "window_minutes": 10},
            )

    async def _check_referral_engine_health(self, ctx: dict[str, Any]) -> None:
        """Alert when referral jobs repeatedly fail."""

        db: AsyncSession = ctx["db"]
        tenant = await self._get_default_tenant(db)
        if tenant is None:
            return

        logs = await db.execute(
            select(SupervisorLog)
            .where(SupervisorLog.event_type == "referral_job_failed")
            .order_by(desc(SupervisorLog.created_at))
            .limit(50)
        )
        fail_counts: dict[str, int] = {}
        for item in logs.scalars().all():
            job_id = str(item.payload.get("job_id") or "unknown")
            fail_counts[job_id] = fail_counts.get(job_id, 0) + 1

        if any(count >= 3 for count in fail_counts.values()):
            await self._emit(db, tenant, "referral_engine_health", "medium", {"fail_counts": fail_counts})

    async def _check_copilot_error_rate(self, ctx: dict[str, Any]) -> None:
        """Check copilot model availability and alert active sessions if down."""

        db: AsyncSession = ctx["db"]
        tenant = await self._get_default_tenant(db)
        if tenant is None:
            return

        unavailable = False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10.0)
                if resp.status_code != 200:
                    unavailable = True
                else:
                    payload = resp.json()
                    models = [m.get("name") for m in payload.get("models", []) if isinstance(m, dict)]
                    if settings.COPILOT_MODEL not in models:
                        unavailable = True
        except Exception:
            unavailable = True

        if unavailable:
            session_count_result = await db.execute(select(func.count()).select_from(ChatSession))
            active_sessions = int(session_count_result.scalar_one())
            await self._emit(
                db,
                tenant,
                "copilot_model_unavailable",
                "high",
                {
                    "model": settings.COPILOT_MODEL,
                    "active_sessions_notified": active_sessions,
                },
            )
