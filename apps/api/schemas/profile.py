"""User profile schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserProfileCreate(BaseModel):
    """Create profile payload."""

    first_name: str
    last_name: str
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    current_location: str | None = None
    work_authorization: str
    target_roles: list[str] = []
    target_locations: list[str] = []
    target_salary_min: float | None = None
    target_salary_max: float | None = None
    years_experience: int | None = None
    summary_bio: str | None = None
    headline: str | None = None


class UserProfileResponse(UserProfileCreate):
    """Profile response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class UserProfilePatch(BaseModel):
    """Partial update payload for profile."""

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    current_location: str | None = None
    work_authorization: str | None = None
    target_roles: list[str] | None = None
    target_locations: list[str] | None = None
    target_salary_min: float | None = None
    target_salary_max: float | None = None
    years_experience: int | None = None
    summary_bio: str | None = None
    headline: str | None = None
