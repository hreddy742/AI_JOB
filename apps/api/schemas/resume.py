"""Resume schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResumeResponse(BaseModel):
    """Resume response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    version: int
    label: str
    is_primary: bool
    file_name: str
    file_size_bytes: int
    file_type: str
    original_text: str
    raw_text: str | None = None
    parse_status: str
    parse_error: str | None = None
    parse_version: int
    parsed_json: dict[str, Any] | None
    embedding_id: str | None
    file_path: str | None
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool


class TailorRequest(BaseModel):
    """Tailoring request payload."""

    resume_id: UUID | None = None
    job_id: UUID
    job_description: str | None = None


class TailorTaskResponse(BaseModel):
    """Background task response for tailoring."""

    task_id: str


class TailoredResumeResponse(BaseModel):
    """Tailored resume payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    job_id: UUID | None
    source_resume_id: UUID
    job_title_target: str | None = None
    company_target: str | None = None
    tailored_text: str
    tailored_parsed: dict[str, Any] | None = None
    diff_log: list[dict[str, Any]]
    ats_score: float | None = None
    quality_score: float | None = None
    violation_count: int = 0
    review_report: dict[str, Any] | None = None
    supervisor_decision: str | None = None
    reviewer_score: float | None
    supervisor_approved: bool
    violations: list[dict[str, Any]]
    retry_count: int
    generation_model: str | None = None
    status: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ResumeUpdateRequest(BaseModel):
    label: str | None = None
    is_primary: bool | None = None


class CoverLetterRequest(BaseModel):
    job_id: UUID | None = None
    tone: str = "professional"
    hiring_manager_name: str | None = None


class CoverLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    source_resume_id: UUID
    tailored_resume_id: UUID | None
    job_id: UUID | None
    job_title_target: str | None
    company_target: str | None
    hiring_manager_name: str | None
    tone: str
    content: str
    word_count: int | None
    generation_model: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    tenant_id: UUID
    resume_id: UUID
    review_type: str
    overall_score: float | None
    ats_score: float | None
    impact_score: float | None
    clarity_score: float | None
    completeness_score: float | None
    format_score: float | None
    full_report: dict[str, Any]
    summary_text: str | None
    key_issues: list[dict[str, Any]]
    quick_wins: list[dict[str, Any]]
    model_used: str | None
    created_at: datetime


class ResumeEditRequest(BaseModel):
    section: str
    field_path: str
    original_value: str
    new_value: str
    change_summary: str | None = None


class ResumeVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    resume_id: UUID
    version_number: int
    content_text: str
    content_parsed: dict[str, Any] | None
    change_summary: str | None
    created_at: datetime


class ImproveBulletRequest(BaseModel):
    section: str
    bullet_index: int
    original: str
    target_role: str | None = None


class ResumeBuildRequest(BaseModel):
    payload: dict[str, Any]
