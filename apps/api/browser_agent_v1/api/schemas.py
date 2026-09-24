"""Pydantic schemas for Browser Agent V1."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrowserAgentRunCreateRequest(BaseModel):
    job_id: UUID
    application_id: UUID | None = None
    resume_id: UUID | None = None
    tailored_resume_id: UUID | None = None
    consent_acknowledged: bool = False


class BrowserAgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    application_id: UUID | None
    job_id: UUID
    resume_id: UUID | None
    tailored_resume_id: UUID | None
    status: str
    current_state: str
    provider: str
    ats_type: str
    entry_url: str
    current_url: str | None
    submit_mode: str
    consent_acknowledged: bool
    latest_perception: dict[str, Any]
    latest_plan: dict[str, Any]
    final_review_summary: dict[str, Any]
    feature_flag_snapshot: dict[str, Any]
    started_at: datetime | None
    last_heartbeat_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class BrowserAgentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    sequence: int
    page_state: str
    action_kind: str
    status: str
    selector: str | None
    detail: str | None
    payload: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime


class BrowserAgentPauseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    page_state: str
    reason_code: str
    status: str
    prompt: str
    requested_data: dict[str, Any]
    response_data: dict[str, Any]
    resolved_at: datetime | None
    created_at: datetime


class BrowserAgentPauseResponseRequest(BaseModel):
    response_data: dict[str, Any] = Field(default_factory=dict)


class BrowserAgentArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    artifact_type: str
    storage_path: str | None
    content_type: str
    inline_text: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class BrowserAgentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    actor: str
    event_type: str
    from_state: str | None
    to_state: str | None
    level: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class BrowserAgentReviewSummaryResponse(BaseModel):
    summary: dict[str, Any]


class BrowserAgentCompatibilityResponse(BaseModel):
    items: list[dict[str, Any]]


class BrowserAgentReplayBundleResponse(BaseModel):
    bundle: dict[str, Any]
