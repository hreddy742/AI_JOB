"""Analytics API routes."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.application import Application
from db.models.chat_session import ChatSession
from db.models.referral import ReferralSuggestion
from db.models.resume import TailoredResume

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _role_guard_admin(token: TokenPayload) -> None:
    """Ensure caller is admin."""

    if token.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


@router.get("/overview")
async def analytics_overview(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return high-level job hunt metrics."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    total = await db.execute(select(func.count()).select_from(Application).where(Application.user_id == user_id))
    submitted = await db.execute(
        select(func.count()).select_from(Application).where(Application.user_id == user_id, Application.status == "submitted")
    )
    interviews = await db.execute(
        select(func.count()).select_from(Application).where(Application.user_id == user_id, Application.status == "interviewing")
    )
    return {
        "applications_total": int(total.scalar_one()),
        "submitted": int(submitted.scalar_one()),
        "interviewing": int(interviews.scalar_one()),
    }


@router.get("/funnel")
async def analytics_funnel(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return application funnel counts by status."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(Application.status, func.count()).where(Application.user_id == user_id).group_by(Application.status))
    return {str(status.value if hasattr(status, 'value') else status): int(count) for status, count in result.all()}


@router.get("/agents")
async def analytics_agents(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only agent quality metrics."""

    await _role_guard_admin(token)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(func.avg(TailoredResume.reviewer_score), func.count()).where(TailoredResume.tenant_id == tenant_id))
    avg_score, count = result.one()
    return {"avg_reviewer_score": float(avg_score or 0.0), "tailored_resume_count": int(count)}


@router.get("/copilot")
async def analytics_copilot(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return copilot usage metrics."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    sessions = await db.execute(select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.tenant_id == tenant_id))
    rows = sessions.scalars().all()
    mode_counts = Counter(str(row.mode.value if hasattr(row.mode, "value") else row.mode) for row in rows)
    avg_turns = 0.0
    if rows:
        avg_turns = sum(len(row.messages or []) for row in rows) / len(rows)

    return {
        "session_count": len(rows),
        "avg_turns": round(avg_turns, 2),
        "popular_modes": dict(mode_counts),
    }


@router.get("/referrals")
async def analytics_referrals(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return referral discovery and conversion metrics."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    total_result = await db.execute(
        select(func.count()).select_from(ReferralSuggestion).where(
            ReferralSuggestion.user_id == user_id,
            ReferralSuggestion.tenant_id == tenant_id,
        )
    )
    converted_result = await db.execute(
        select(func.count()).select_from(ReferralSuggestion).where(
            ReferralSuggestion.user_id == user_id,
            ReferralSuggestion.tenant_id == tenant_id,
            ReferralSuggestion.status == "converted",
        )
    )

    total = int(total_result.scalar_one())
    converted = int(converted_result.scalar_one())
    conversion_rate = (converted / total) if total else 0.0
    return {
        "discovery_rate": total,
        "conversion_count": converted,
        "conversion_rate": round(conversion_rate, 4),
    }
