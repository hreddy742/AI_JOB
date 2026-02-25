"""Application routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_token, get_db
from core.security import TokenPayload
from schemas.application import ApplicationCreate, ApplicationResponse, ApplicationUpdate
from services.application_service import (
    create_application,
    get_application,
    get_automation_audit,
    list_applications,
    queue_automation,
    update_application,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationResponse)
async def create_application_endpoint(
    payload: ApplicationCreate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Create a new application."""

    app = await create_application(db, token, payload)
    return ApplicationResponse.model_validate(app)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications_endpoint(
    status: str | None = Query(default=None),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationResponse]:
    """List applications for current user."""

    apps = await list_applications(db, token, status)
    return [ApplicationResponse.model_validate(app) for app in apps]


@router.get("/{id}", response_model=ApplicationResponse)
async def get_application_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Get one application with automation log."""

    app = await get_application(db, token, id)
    return ApplicationResponse.model_validate(app)


@router.patch("/{id}", response_model=ApplicationResponse)
async def patch_application_endpoint(
    id: UUID,
    payload: ApplicationUpdate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Patch application."""

    app = await update_application(db, token, id, payload)
    return ApplicationResponse.model_validate(app)


@router.post("/{id}/automate")
async def automate_application_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Queue safe automation task."""

    task_id = await queue_automation(db, token, id)
    return {"task_id": task_id}


@router.get("/{id}/audit")
async def application_audit_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get application automation audit data."""

    return await get_automation_audit(db, token, id)
