"""Referral API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_token, get_db
from core.security import TokenPayload
from schemas.outreach import ContactResponse
from schemas.referral import (
    ReferralDiscoverRequest,
    ReferralResponse,
    ReferralTaskResponse,
    ReferralUpdate,
)
from services.referral_service import (
    convert_referral_to_contact,
    get_task_status,
    list_referrals,
    queue_discovery,
    update_referral_status,
)

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.post("/discover", response_model=ReferralTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def discover_referrals(
    payload: ReferralDiscoverRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ReferralTaskResponse:
    """Queue referral discovery for a specific job."""

    task_id = await queue_discovery(db, token, payload.job_id)
    return ReferralTaskResponse(task_id=task_id)


@router.get("/discover/{task_id}/status")
async def get_discover_status(task_id: str) -> dict:
    """Return referral discovery task status."""

    return await get_task_status(task_id)


@router.get("", response_model=list[ReferralResponse])
async def list_referral_suggestions(
    job_id: UUID | None = Query(default=None),
    company: str | None = Query(default=None),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ReferralResponse]:
    """List referral suggestions for authenticated user."""

    items = await list_referrals(db, token, job_id=job_id, company=company)
    return [ReferralResponse.model_validate(item) for item in items]


@router.patch("/{id}", response_model=ReferralResponse)
async def patch_referral_status(
    id: UUID,
    payload: ReferralUpdate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ReferralResponse:
    """Update referral suggestion status."""

    item = await update_referral_status(db, token, id, payload.status)
    return ReferralResponse.model_validate(item)


@router.post("/{id}/convert", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def convert_referral(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Convert referral suggestion into CRM contact."""

    contact = await convert_referral_to_contact(db, token, id)
    return ContactResponse.model_validate(contact)
