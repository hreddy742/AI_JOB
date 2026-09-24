"""Campaign stage runner service with persisted resumable stages."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import TokenPayload
from db.models.application import Application
from db.models.application_campaign_stage import ApplicationCampaignStage

CAMPAIGN_STAGES: tuple[str, ...] = (
    "discovered",
    "shortlisted",
    "tailored",
    "applied",
    "interviewing",
    "offered",
    "rejected",
)
_STAGE_INDEX = {stage: idx for idx, stage in enumerate(CAMPAIGN_STAGES)}


def _is_valid_transition(current: str, next_stage: str) -> bool:
    if current == next_stage:
        return True
    if next_stage not in _STAGE_INDEX or current not in _STAGE_INDEX:
        return False
    # Allow forward-only progression; rejected/offered are terminal except idempotent updates.
    if current in {"offered", "rejected"}:
        return False
    return _STAGE_INDEX[next_stage] >= _STAGE_INDEX[current]


async def _get_owned_application(db: AsyncSession, token: TokenPayload, application_id: UUID) -> Application:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    return await _get_owned_application_scoped(db, tenant_id=tenant_id, user_id=user_id, application_id=application_id)


async def _get_owned_application_scoped(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    application_id: UUID,
) -> Application:
    app = (
        await db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.user_id == user_id,
                Application.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def get_or_create_campaign_stage(db: AsyncSession, token: TokenPayload, application_id: UUID) -> ApplicationCampaignStage:
    app = await _get_owned_application(db, token, application_id)
    return await get_or_create_campaign_stage_scoped(
        db,
        tenant_id=app.tenant_id,
        user_id=app.user_id,
        application_id=app.id,
    )


async def get_or_create_campaign_stage_scoped(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    application_id: UUID,
) -> ApplicationCampaignStage:
    app = await _get_owned_application_scoped(db, tenant_id=tenant_id, user_id=user_id, application_id=application_id)
    row = (
        await db.execute(
            select(ApplicationCampaignStage).where(ApplicationCampaignStage.application_id == app.id)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    now = datetime.now(UTC)
    row = ApplicationCampaignStage(
        application_id=app.id,
        tenant_id=app.tenant_id,
        user_id=app.user_id,
        current_stage="discovered",
        stage_history=[{"stage": "discovered", "at": now.isoformat(), "event": "initialized"}],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def advance_campaign_stage(
    db: AsyncSession,
    token: TokenPayload,
    application_id: UUID,
    next_stage: str,
    note: str | None = None,
    resumed: bool = False,
) -> ApplicationCampaignStage:
    return await advance_campaign_stage_scoped(
        db,
        tenant_id=UUID(token.tenant_id),
        user_id=UUID(token.sub),
        application_id=application_id,
        next_stage=next_stage,
        note=note,
        resumed=resumed,
    )


async def advance_campaign_stage_scoped(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    application_id: UUID,
    next_stage: str,
    note: str | None = None,
    resumed: bool = False,
) -> ApplicationCampaignStage:
    normalized = (next_stage or "").strip().lower()
    if normalized not in _STAGE_INDEX:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid campaign stage")

    row = await get_or_create_campaign_stage_scoped(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        application_id=application_id,
    )
    current = row.current_stage
    if not _is_valid_transition(current, normalized):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid stage transition: {current} -> {normalized}",
        )

    now = datetime.now(UTC)
    row.current_stage = normalized
    history = list(row.stage_history or [])
    history.append({"stage": normalized, "at": now.isoformat(), "event": "resumed" if resumed else "advanced", "note": note or ""})
    row.stage_history = history
    if resumed:
        row.resumed_at = now
    await db.commit()
    await db.refresh(row)
    return row
