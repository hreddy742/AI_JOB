"""User notification helpers for Browser Agent V1 lifecycle events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.browser_agent_run import BrowserAgentRun
from db.models.job import Job
from db.models.user import User
from services.email_service import (
    send_browser_agent_failed_email,
    send_browser_agent_pause_email,
    send_browser_agent_review_email,
)


async def _load_notification_context(db: AsyncSession, run: BrowserAgentRun) -> tuple[User | None, Job | None]:
    user = (
        await db.execute(select(User).where(User.id == UUID(str(run.user_id)), User.tenant_id == run.tenant_id))
    ).scalar_one_or_none()
    job = (await db.execute(select(Job).where(Job.id == run.job_id, Job.tenant_id == run.tenant_id))).scalar_one_or_none()
    return user, job


async def notify_browser_agent_paused(db: AsyncSession, run: BrowserAgentRun, *, prompt: str) -> None:
    user, job = await _load_notification_context(db, run)
    if user is None or job is None:
        return
    await send_browser_agent_pause_email(
        to_email=user.email,
        full_name=user.full_name or "",
        job_title=job.title,
        company=job.company,
        run_id=str(run.id),
        prompt=prompt,
    )


async def notify_browser_agent_review_required(db: AsyncSession, run: BrowserAgentRun) -> None:
    user, job = await _load_notification_context(db, run)
    if user is None or job is None:
        return
    await send_browser_agent_review_email(
        to_email=user.email,
        full_name=user.full_name or "",
        job_title=job.title,
        company=job.company,
        run_id=str(run.id),
    )


async def notify_browser_agent_failed(db: AsyncSession, run: BrowserAgentRun) -> None:
    user, job = await _load_notification_context(db, run)
    if user is None or job is None:
        return
    await send_browser_agent_failed_email(
        to_email=user.email,
        full_name=user.full_name or "",
        job_title=job.title,
        company=job.company,
        run_id=str(run.id),
        error_detail=str(run.error_detail or run.error_code or "Browser Agent V1 run failed."),
    )
