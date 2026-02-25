"""User profile CRUD routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.user_profile import UserProfile
from schemas.profile import UserProfileCreate, UserProfilePatch, UserProfileResponse

router = APIRouter(prefix="/profile", tags=["profile"])


def _parse_user_context(token: TokenPayload) -> tuple[UUID, UUID]:
    """Parse user and tenant UUIDs from auth token payload."""

    try:
        return UUID(token.sub), UUID(token.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token identity") from exc


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Return the authenticated user's profile."""

    user_id, tenant_id = _parse_user_context(token)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return UserProfileResponse.model_validate(profile)


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: UserProfileCreate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Create a profile for the authenticated user."""

    user_id, tenant_id = _parse_user_context(token)
    await apply_tenant_rls(db, tenant_id)

    existing = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Profile already exists")

    profile = UserProfile(
        user_id=user_id,
        tenant_id=tenant_id,
        **payload.model_dump(),
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return UserProfileResponse.model_validate(profile)


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    payload: UserProfileCreate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Replace the authenticated user's profile."""

    user_id, tenant_id = _parse_user_context(token)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(profile)
    return UserProfileResponse.model_validate(profile)


@router.patch("", response_model=UserProfileResponse)
async def patch_profile(
    payload: UserProfilePatch,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Partially update authenticated user's profile."""

    user_id, tenant_id = _parse_user_context(token)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(profile)
    return UserProfileResponse.model_validate(profile)
