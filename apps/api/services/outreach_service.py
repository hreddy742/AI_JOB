"""Outreach and contact service layer with compliance rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.outreach_graph import compiled_outreach_graph
from core.config import settings
from core.dependencies import apply_tenant_rls
from core.security import TokenPayload
from db.models.contact import Contact
from db.models.job import Job
from db.models.outreach import OutreachMessage
from db.models.resume import Resume
from db.models.user_profile import UserProfile
from schemas.outreach import ContactCreate


def _redis_client() -> redis.Redis:
    """Build async Redis client."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def _send_limit_key(user_id: UUID) -> str:
    """Compute daily outreach send key for user."""

    return f"ratelimit:outreach:{user_id}:{datetime.now(UTC).date().isoformat()}"


async def create_contact(db: AsyncSession, token: TokenPayload, payload: ContactCreate) -> Contact:
    """Create CRM contact."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    contact = Contact(user_id=user_id, tenant_id=tenant_id, **payload.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def list_contacts(db: AsyncSession, token: TokenPayload) -> list[Contact]:
    """List contacts for authenticated user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(Contact).where(Contact.user_id == user_id, Contact.tenant_id == tenant_id))
    return result.scalars().all()


async def delete_contact(db: AsyncSession, token: TokenPayload, contact_id: UUID) -> None:
    """Delete a contact by ID."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id, Contact.tenant_id == tenant_id)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    await db.delete(contact)
    await db.commit()


async def _get_profile_and_resume(db: AsyncSession, user_id: UUID, tenant_id: UUID) -> tuple[UserProfile, Resume | None]:
    """Fetch profile and latest resume for outreach context."""

    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id, UserProfile.tenant_id == tenant_id))
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile required before outreach")

    resume_result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.tenant_id == tenant_id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = resume_result.scalar_one_or_none()
    return profile, resume


async def draft_outreach(db: AsyncSession, token: TokenPayload, contact_id: UUID, job_id: UUID | None) -> OutreachMessage:
    """Generate outreach draft and compliance score."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    contact_result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id, Contact.tenant_id == tenant_id)
    )
    contact = contact_result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    job = None
    if job_id is not None:
        job_result = await db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))
        job = job_result.scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    profile, resume = await _get_profile_and_resume(db, user_id, tenant_id)

    state = {
        "contact": {
            "name": contact.name,
            "company": contact.company,
            "title": contact.title,
        },
        "job": {
            "title": job.title,
            "company": job.company,
            "description": job.description,
        }
        if job
        else None,
        "resume_summary": (resume.original_text[:1000] if resume else ""),
        "user_profile": {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "headline": profile.headline,
        },
        "draft_text": "",
        "compliance_report": {},
    }

    result = await compiled_outreach_graph.ainvoke(state)
    report = result.get("compliance_report") or {}

    message = OutreachMessage(
        user_id=user_id,
        tenant_id=tenant_id,
        contact_id=contact_id,
        job_id=job_id,
        draft_text=result.get("draft_text") or "",
        compliance_score=float(report.get("score") or 0.0),
        status="draft",
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def list_outreach(db: AsyncSession, token: TokenPayload) -> list[OutreachMessage]:
    """List outreach messages for user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.user_id == user_id, OutreachMessage.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def get_outreach(db: AsyncSession, token: TokenPayload, message_id: UUID) -> OutreachMessage:
    """Get one outreach message by id."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(OutreachMessage).where(
            OutreachMessage.id == message_id,
            OutreachMessage.user_id == user_id,
            OutreachMessage.tenant_id == tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach message not found")
    return item


async def patch_outreach(db: AsyncSession, token: TokenPayload, message_id: UUID, draft_text: str | None) -> OutreachMessage:
    """Update outreach draft and force re-approval if previously approved."""

    item = await get_outreach(db, token, message_id)
    if draft_text is not None:
        if item.status == "approved":
            item.status = "draft"
            item.approved_at = None
        item.draft_text = draft_text
    await db.commit()
    await db.refresh(item)
    return item


async def approve_outreach(db: AsyncSession, token: TokenPayload, message_id: UUID) -> OutreachMessage:
    """Approve outreach message for sending."""

    item = await get_outreach(db, token, message_id)
    item.status = "approved"
    item.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(item)
    return item


async def send_outreach(db: AsyncSession, token: TokenPayload, message_id: UUID) -> OutreachMessage:
    """Send outreach message with compliance hard-rule enforcement."""

    item = await get_outreach(db, token, message_id)

    if item.status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message must be approved before send")

    if item.approved_at is None or item.approved_at < datetime.now(UTC) - timedelta(hours=24):
        item.status = "draft"
        item.approved_at = None
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval expired; re-approval required")

    redis_client = _redis_client()
    key = _send_limit_key(UUID(token.sub))
    count = await redis_client.incr(key)
    if count == 1:
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).date()
        midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)
        await redis_client.expire(key, int((midnight - now).total_seconds()))

    if count > settings.OUTREACH_MAX_PER_DAY:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily outreach send limit reached")

    item.status = "sent"
    item.sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(item)
    return item
