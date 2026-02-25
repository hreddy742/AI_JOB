"""Copilot schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatSessionCreate(BaseModel):
    """Create chat session payload."""

    title: str | None = None
    mode: str = "general"
    job_id: UUID | None = None
    resume_id: UUID | None = None


class ChatSessionResponse(BaseModel):
    """Chat session response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    title: str | None
    mode: str
    job_id: UUID | None
    resume_id: UUID | None
    messages: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CopilotMessageRequest(BaseModel):
    """Send copilot message payload."""

    message: str


class CopilotModeUpdate(BaseModel):
    """Switch copilot mode payload."""

    mode: str


class InterviewQuestion(BaseModel):
    """Interview question payload."""

    category: str
    question: str
    tips: str | None = None
