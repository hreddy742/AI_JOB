"""Outreach and contact schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContactCreate(BaseModel):
    """Create contact payload."""

    name: str | None = None
    title: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    source: str | None = None
    notes: str | None = None


class ContactResponse(ContactCreate):
    """Contact response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    email_verified: bool
    created_at: datetime


class OutreachDraftRequest(BaseModel):
    """Request for drafting outreach message."""

    contact_id: UUID
    job_id: UUID | None = None


class OutreachResponse(BaseModel):
    """Outreach message response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    contact_id: UUID
    job_id: UUID | None
    draft_text: str
    compliance_score: float | None
    status: str
    approved_at: datetime | None
    sent_at: datetime | None
    reply_received_at: datetime | None
    created_at: datetime
