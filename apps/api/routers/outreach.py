"""Outreach and contacts routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_token, get_db
from core.security import TokenPayload
from schemas.outreach import ContactCreate, ContactResponse, OutreachDraftRequest, OutreachResponse
from services.outreach_service import (
    approve_outreach,
    create_contact,
    delete_contact,
    draft_outreach,
    get_outreach,
    list_contacts,
    list_outreach,
    patch_outreach,
    send_outreach,
)

router = APIRouter(tags=["outreach"])


@router.post("/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_endpoint(
    payload: ContactCreate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Create CRM contact."""

    item = await create_contact(db, token, payload)
    return ContactResponse.model_validate(item)


@router.get("/contacts", response_model=list[ContactResponse])
async def list_contacts_endpoint(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ContactResponse]:
    """List contacts for current user."""

    items = await list_contacts(db, token)
    return [ContactResponse.model_validate(item) for item in items]


@router.delete("/contacts/{id}", status_code=status.HTTP_200_OK)
async def delete_contact_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete contact."""

    await delete_contact(db, token, id)
    return {"status": "deleted"}


@router.post("/outreach/draft", response_model=OutreachResponse, status_code=status.HTTP_201_CREATED)
async def draft_outreach_endpoint(
    payload: OutreachDraftRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> OutreachResponse:
    """Draft outreach message via graph."""

    item = await draft_outreach(db, token, payload.contact_id, payload.job_id)
    return OutreachResponse.model_validate(item)


@router.get("/outreach", response_model=list[OutreachResponse])
async def list_outreach_endpoint(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[OutreachResponse]:
    """List outreach messages."""

    items = await list_outreach(db, token)
    return [OutreachResponse.model_validate(item) for item in items]


@router.patch("/outreach/{id}", response_model=OutreachResponse)
async def patch_outreach_endpoint(
    id: UUID,
    draft_text: str | None = None,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> OutreachResponse:
    """Edit outreach draft; approved messages are reset to draft."""

    item = await patch_outreach(db, token, id, draft_text)
    return OutreachResponse.model_validate(item)


@router.post("/outreach/{id}/approve", response_model=OutreachResponse)
async def approve_outreach_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> OutreachResponse:
    """Approve outreach message."""

    item = await approve_outreach(db, token, id)
    return OutreachResponse.model_validate(item)


@router.post("/outreach/{id}/send", response_model=OutreachResponse)
async def send_outreach_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> OutreachResponse:
    """Send outreach message with hard compliance rules."""

    item = await send_outreach(db, token, id)
    return OutreachResponse.model_validate(item)


@router.get("/outreach/{id}", response_model=OutreachResponse)
async def get_outreach_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> OutreachResponse:
    """Get one outreach message."""

    item = await get_outreach(db, token, id)
    return OutreachResponse.model_validate(item)
