"""Application schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    """Create application payload."""

    job_id: UUID
    tailored_resume_id: UUID | None = None
    notes: str | None = None
    follow_up_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    """Partial update payload for applications."""

    status: str | None = None
    notes: str | None = None
    follow_up_at: datetime | None = None


class ApplicationResponse(BaseModel):
    """Application response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    job_id: UUID
    tailored_resume_id: UUID | None
    status: str
    applied_at: datetime | None
    automation_log: list[dict[str, Any]]
    notes: str | None
    follow_up_at: datetime | None
    created_at: datetime
