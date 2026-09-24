"""In-app alerts routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, apply_user_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.alert_log import AlertLog
from db.models.job import Job
from db.models.user_profile import UserProfile

router = APIRouter(prefix="/alerts", tags=["alerts"])


async def _context(db: AsyncSession, token: TokenPayload) -> tuple[UUID, UUID]:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    return user_id, tenant_id


@router.get("")
async def list_alerts(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return in-app alerts and preferences."""

    user_id, tenant_id = await _context(db, token)
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user_id, UserProfile.tenant_id == tenant_id))
    ).scalar_one_or_none()
    rows = (
        await db.execute(
            select(AlertLog).where(AlertLog.user_id == user_id, AlertLog.tenant_id == tenant_id).order_by(AlertLog.created_at.desc())
        )
    ).scalars().all()

    items: list[dict] = []
    for row in rows:
        job = None
        if row.job_id is not None:
            job = (await db.execute(select(Job).where(Job.id == row.job_id))).scalar_one_or_none()
        payload = row.payload or {}
        items.append(
            {
                "id": str(row.id),
                "alert_type": row.alert_type,
                "title": row.title,
                "message": row.message,
                "is_read": row.is_read,
                "timestamp": row.created_at.isoformat(),
                "job_title": payload.get("job_title") or (job.title if job else row.title),
                "company": payload.get("company") or (job.company if job else ""),
                "location": payload.get("location")
                or (", ".join(filter(None, [getattr(job, "location_city", None), getattr(job, "location_state", None)])) if job else ""),
                "sponsorship_status": payload.get("sponsorship_status") or (getattr(job, "sponsorship_status", None) if job else "unknown"),
                "sponsorship_confidence": payload.get("sponsorship_confidence") or (float(getattr(job, "sponsorship_confidence", 0.0) or 0.0) if job else 0.0),
                "h1b_score": payload.get("h1b_score") or payload.get("confidence_score"),
            }
        )

    return {
        "items": items,
        "alerts": items,
        "preferences": {
            "alerts_active": bool(profile.alerts_active) if profile else True,
            "alert_budget_per_day": int(profile.alert_budget_per_day) if profile and profile.alert_budget_per_day is not None else 10,
        },
        "unread_count": sum(1 for item in items if not item["is_read"]),
    }


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark one alert as read."""

    user_id, tenant_id = await _context(db, token)
    row = (
        await db.execute(
            select(AlertLog).where(AlertLog.id == alert_id, AlertLog.user_id == user_id, AlertLog.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is not None:
        row.is_read = True
        row.read_at = datetime.now(UTC)
        await db.commit()
    return {"status": "ok"}


@router.delete("/read")
async def clear_read_alerts(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all read alerts."""

    user_id, tenant_id = await _context(db, token)
    await db.execute(delete(AlertLog).where(AlertLog.user_id == user_id, AlertLog.tenant_id == tenant_id, AlertLog.is_read.is_(True)))
    await db.commit()
    return {"status": "ok"}


@router.delete("/read-all")
async def clear_read_alerts_alias(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all seen alerts using the explicit read-all alias."""

    return await clear_read_alerts(token=token, db=db)


@router.put("/preferences")
async def update_alert_preferences(
    payload: dict,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update alert preferences using existing user profile fields."""

    user_id, tenant_id = await _context(db, token)
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user_id, UserProfile.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if profile is None:
        profile = UserProfile(
            user_id=user_id,
            tenant_id=tenant_id,
            first_name="",
            last_name="",
            work_authorization="unknown",
        )
        db.add(profile)

    if "alerts_active" in payload:
        profile.alerts_active = bool(payload.get("alerts_active"))
    if "alert_budget_per_day" in payload:
        profile.alert_budget_per_day = max(1, min(int(payload.get("alert_budget_per_day") or 10), 50))
    await db.commit()
    return {"ok": True, "alerts_active": bool(profile.alerts_active), "alert_budget_per_day": int(profile.alert_budget_per_day or 10)}
