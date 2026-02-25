"""Application service layer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as redis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls
from core.security import TokenPayload
from db.models.application import Application
from db.models.job import Job
from db.session import AsyncSessionFactory
from schemas.application import ApplicationCreate, ApplicationUpdate

_TASKS: dict[str, dict[str, Any]] = {}


def _redis_client() -> redis.Redis:
    """Return async redis client."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def create_application(db: AsyncSession, token: TokenPayload, payload: ApplicationCreate) -> Application:
    """Create a new application in draft status."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    job_result = await db.execute(select(Job).where(Job.id == payload.job_id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    application = Application(
        user_id=user_id,
        tenant_id=tenant_id,
        job_id=payload.job_id,
        tailored_resume_id=payload.tailored_resume_id,
        notes=payload.notes,
        follow_up_at=payload.follow_up_at,
        status="draft",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


async def list_applications(db: AsyncSession, token: TokenPayload, status_filter: str | None = None) -> list[Application]:
    """List applications for user with optional status filter."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    query = select(Application).where(Application.user_id == user_id, Application.tenant_id == tenant_id)
    if status_filter:
        query = query.where(Application.status == status_filter)
    result = await db.execute(query.order_by(Application.created_at.desc()))
    return result.scalars().all()


async def get_application(db: AsyncSession, token: TokenPayload, application_id: UUID) -> Application:
    """Get application by id for current user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
            Application.tenant_id == tenant_id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def update_application(
    db: AsyncSession,
    token: TokenPayload,
    application_id: UUID,
    payload: ApplicationUpdate,
) -> Application:
    """Patch an application and append audit entry."""

    app = await get_application(db, token, application_id)
    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(app, key, value)

    if updates.get("status") == "submitted" and app.applied_at is None:
        app.applied_at = datetime.now(UTC)

    log = list(app.automation_log or [])
    log.append({"ts": datetime.now(UTC).isoformat(), "event": "application_updated", "changes": updates})
    app.automation_log = log

    await db.commit()
    await db.refresh(app)
    return app


async def _set_task(task_id: str, payload: dict[str, Any]) -> None:
    """Persist task status in memory and redis."""

    _TASKS[task_id] = payload
    client = _redis_client()
    await client.set(f"application:automate:{task_id}", str(payload), ex=3600)


async def _run_automation_task(task_id: str, application_id: UUID) -> None:
    """Run queued automation task."""

    from workers.automation_worker import automate_application

    await _set_task(task_id, {"task_id": task_id, "status": "running"})
    async with AsyncSessionFactory() as db:
        result = await automate_application({"db": db}, str(application_id))
    await _set_task(task_id, {"task_id": task_id, "status": "completed", "result": result})


async def queue_automation(db: AsyncSession, token: TokenPayload, application_id: UUID) -> str:
    """Queue automation for a draft application."""

    app = await get_application(db, token, application_id)
    task_id = str(uuid4())

    log = list(app.automation_log or [])
    log.append({"ts": datetime.now(UTC).isoformat(), "event": "automation_queued", "task_id": task_id})
    app.automation_log = log
    await db.commit()

    await _set_task(task_id, {"task_id": task_id, "status": "queued", "application_id": str(application_id)})
    asyncio.create_task(_run_automation_task(task_id, application_id))
    return task_id


async def get_automation_audit(db: AsyncSession, token: TokenPayload, application_id: UUID) -> dict[str, Any]:
    """Get automation audit trail for application."""

    app = await get_application(db, token, application_id)
    return {
        "application_id": str(app.id),
        "status": app.status.value if hasattr(app.status, "value") else str(app.status),
        "automation_log": app.automation_log or [],
    }
