"""OPT tracker routes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, apply_user_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.alert_log import AlertLog
from db.models.opt_tracker import OptTracker

router = APIRouter(prefix="/opt", tags=["opt"])


def _urgency(days_remaining: int | None) -> str:
    if days_remaining is None:
        return "normal"
    if days_remaining <= 14:
        return "critical"
    if days_remaining <= 60:
        return "elevated"
    return "normal"


def _days_until(target: date | None) -> int | None:
    if target is None:
        return None
    return (target - datetime.now(UTC).date()).days


def _status_payload(row: OptTracker | None) -> dict:
    configured = row is not None and row.opt_end_date is not None
    effective_end = row.stem_opt_end if row and row.stem_opt_eligible and row.stem_opt_end else (row.opt_end_date if row else None)
    days_remaining = _days_until(effective_end)
    urgency = _urgency(days_remaining)
    return {
        "configured": configured,
        "opt_start_date": row.opt_start_date.isoformat() if row and row.opt_start_date else None,
        "opt_end_date": row.opt_end_date.isoformat() if row and row.opt_end_date else None,
        "stem_opt_eligible": bool(row.stem_opt_eligible) if row else False,
        "stem_opt_end": row.stem_opt_end.isoformat() if row and row.stem_opt_end else None,
        "stem_applied": bool(row.stem_applied) if row else False,
        "h1b_filed": bool(row.h1b_filed) if row else False,
        "focused_on_h1b_companies": bool(row.focused_on_h1b_companies) if row else False,
        "days_remaining": days_remaining,
        "urgency": urgency.upper(),
        "urgency_level": row.urgency_level if row and row.urgency_level else urgency,
        "stem_extension_reminder": bool(row and row.stem_opt_eligible and (days_remaining is not None and days_remaining <= 90)),
        "checklist": {
            "opt_configured": configured,
            "stem_applied": bool(row.stem_applied) if row else False,
            "h1b_filed": bool(row.h1b_filed) if row else False,
            "focused_on_h1b_companies": bool(row.focused_on_h1b_companies) if row else False,
        },
    }


async def _get_row(db: AsyncSession, token: TokenPayload) -> tuple[UUID, UUID, OptTracker | None]:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    row = (
        await db.execute(select(OptTracker).where(OptTracker.user_id == user_id, OptTracker.tenant_id == tenant_id))
    ).scalar_one_or_none()
    return user_id, tenant_id, row


@router.get("/status")
async def get_opt_status(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current OPT tracker status."""

    _, _, row = await _get_row(db, token)
    return _status_payload(row)


@router.put("/setup")
async def put_opt_setup(
    payload: dict,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update OPT tracker setup."""

    user_id, tenant_id, row = await _get_row(db, token)
    if row is None:
        row = OptTracker(user_id=user_id, tenant_id=tenant_id)
        db.add(row)

    def parse_date(name: str) -> date | None:
        value = payload.get(name)
        return date.fromisoformat(value) if value else None

    row.opt_start_date = parse_date("opt_start_date")
    row.opt_end_date = parse_date("opt_end_date")
    row.stem_opt_eligible = bool(payload.get("stem_opt_eligible"))
    row.stem_opt_end = parse_date("stem_opt_end")
    row.focused_on_h1b_companies = bool(payload.get("focused_on_h1b_companies", row.focused_on_h1b_companies))
    row.stem_applied = bool(payload.get("stem_applied", row.stem_applied))
    row.urgency_level = _urgency(_days_until(row.stem_opt_end if row.stem_opt_eligible and row.stem_opt_end else row.opt_end_date))
    await db.commit()
    await db.refresh(row)

    if row.opt_end_date:
        existing_alert = (
            await db.execute(
                select(AlertLog).where(
                    AlertLog.user_id == user_id,
                    AlertLog.tenant_id == tenant_id,
                    AlertLog.alert_type == "opt_deadline",
                )
            )
        ).scalar_one_or_none()
        if existing_alert is None:
            db.add(
                AlertLog(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    alert_type="opt_deadline",
                    title="OPT tracker configured",
                    message="Deadline alerts are active for your OPT tracker.",
                    payload={"opt_end_date": row.opt_end_date.isoformat()},
                )
            )
            await db.commit()

    return {"ok": True, **_status_payload(row)}


@router.patch("/h1b-filed")
async def patch_h1b_filed(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark H1B as filed."""

    user_id, tenant_id, row = await _get_row(db, token)
    if row is None:
        row = OptTracker(user_id=user_id, tenant_id=tenant_id)
        db.add(row)
    row.h1b_filed = True
    row.urgency_level = _urgency(_days_until(row.stem_opt_end if row.stem_opt_eligible and row.stem_opt_end else row.opt_end_date))
    await db.commit()
    await db.refresh(row)

    db.add(
        AlertLog(
            user_id=user_id,
            tenant_id=tenant_id,
            alert_type="opt_h1b",
            channel="in_app",
            title="H1B filed",
            message="Your OPT checklist now reflects H1B filing.",
            payload={"h1b_filed": True},
            is_read=True,
            read_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return {"ok": True, **_status_payload(row)}
