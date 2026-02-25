"""Referral service functions and task orchestration."""

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
from db.models.contact import Contact
from db.models.job import Job
from db.models.referral import ReferralSuggestion
from db.models.user_profile import UserProfile
from db.session import AsyncSessionFactory

_TASKS: dict[str, dict[str, Any]] = {}
_LOCK = asyncio.Lock()


def _redis_client() -> redis.Redis:
    """Create async Redis client for referral task state."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def _set_task(task_id: str, payload: dict[str, Any]) -> None:
    """Persist task status in memory and Redis."""

    async with _LOCK:
        _TASKS[task_id] = payload

    redis_client = _redis_client()
    await redis_client.set(f"referral:task:{task_id}:status", str(payload), ex=3600)


async def _run_discovery_task(task_id: str, job_id: UUID, user_id: UUID, tenant_id: UUID) -> None:
    """Run referral discovery async task."""

    from workers.referral_worker import discover_referrals_for_job

    await _set_task(task_id, {"task_id": task_id, "status": "running"})
    async with AsyncSessionFactory() as db:
        await apply_tenant_rls(db, tenant_id)
        result = await discover_referrals_for_job(
            {
                "db": db,
                "tenant_id": tenant_id,
            },
            job_id=str(job_id),
            user_id=str(user_id),
        )
    await _set_task(task_id, {"task_id": task_id, "status": "completed", "result": result})


async def queue_discovery(db: AsyncSession, token: TokenPayload, job_id: UUID) -> str:
    """Queue referral discovery for user/job pair."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(Job.id).where(Job.id == job_id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    task_id = str(uuid4())
    await _set_task(task_id, {"task_id": task_id, "status": "queued"})
    asyncio.create_task(_run_discovery_task(task_id, job_id, user_id, tenant_id))
    return task_id


async def get_task_status(task_id: str) -> dict[str, Any]:
    """Get referral discovery task status."""

    async with _LOCK:
        task = _TASKS.get(task_id)
    if task is not None:
        return task

    redis_client = _redis_client()
    raw = await redis_client.get(f"referral:task:{task_id}:status")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"task_id": task_id, "status": "unknown", "raw": raw}


async def list_referrals(
    db: AsyncSession,
    token: TokenPayload,
    job_id: UUID | None = None,
    company: str | None = None,
) -> list[ReferralSuggestion]:
    """List referral suggestions for the authenticated user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    query = select(ReferralSuggestion).where(
        ReferralSuggestion.user_id == user_id,
        ReferralSuggestion.tenant_id == tenant_id,
    )
    if job_id is not None:
        query = query.where(ReferralSuggestion.job_id == job_id)
    if company:
        query = query.where(ReferralSuggestion.company.ilike(f"%{company}%"))

    result = await db.execute(query.order_by(ReferralSuggestion.created_at.desc()))
    return result.scalars().all()


async def update_referral_status(
    db: AsyncSession,
    token: TokenPayload,
    referral_id: UUID,
    status_value: str,
) -> ReferralSuggestion:
    """Update referral suggestion status."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(ReferralSuggestion).where(
            ReferralSuggestion.id == referral_id,
            ReferralSuggestion.user_id == user_id,
            ReferralSuggestion.tenant_id == tenant_id,
        )
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")

    referral.status = status_value
    await db.commit()
    await db.refresh(referral)
    return referral


async def convert_referral_to_contact(
    db: AsyncSession,
    token: TokenPayload,
    referral_id: UUID,
) -> Contact:
    """Convert referral suggestion into CRM contact."""

    # COMPLIANCE: All contacts stored with is_verified=False.
    # inferred_email is labeled as unverified in all API responses.
    # Users are warned in UI before any outreach action.
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    referral_result = await db.execute(
        select(ReferralSuggestion).where(
            ReferralSuggestion.id == referral_id,
            ReferralSuggestion.user_id == user_id,
            ReferralSuggestion.tenant_id == tenant_id,
        )
    )
    referral = referral_result.scalar_one_or_none()
    if referral is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")

    contact = Contact(
        user_id=user_id,
        tenant_id=tenant_id,
        name=referral.contact_name,
        title=referral.contact_title or "Bio hint - not verified",
        company=referral.company,
        email=referral.inferred_email,
        email_verified=False,
        source="referral_engine",
        notes=(
            "Inferred contact converted from referral suggestion. "
            "Email is inferred and not verified."
        ),
    )
    db.add(contact)
    referral.status = "converted"
    await db.commit()
    await db.refresh(contact)
    return contact


async def get_job(job_id: str, db: AsyncSession, tenant_id: UUID) -> Job:
    """Load one job by ID under tenant scope."""

    await apply_tenant_rls(db, tenant_id)
    result = await db.execute(select(Job).where(Job.id == UUID(job_id), Job.tenant_id == tenant_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def get_user_profile(user_id: str, db: AsyncSession, tenant_id: UUID) -> UserProfile:
    """Load profile used by referral scoring context."""

    await apply_tenant_rls(db, tenant_id)
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == UUID(user_id), UserProfile.tenant_id == tenant_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return profile
