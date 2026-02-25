"""Referral schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReferralDiscoverRequest(BaseModel):
    """Request to queue referral discovery."""

    job_id: UUID


class ReferralTaskResponse(BaseModel):
    """Referral task response."""

    task_id: str


class ReferralUpdate(BaseModel):
    """Update referral status payload."""

    status: str


class ReferralResponse(BaseModel):
    """Referral suggestion response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    job_id: UUID
    company: str
    contact_name: str | None
    contact_title: str | None
    contact_source: str | None
    contact_url: str | None
    inferred_email: str | None
    email_pattern: str | None
    confidence_score: float | None
    discovery_method: str | None
    is_verified: bool
    status: str
    created_at: datetime
