"""Resume-related models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class Resume(Base, IdMixin):
    """User uploaded resume."""

    __tablename__ = "resumes"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="My Resume", server_default="My Resume")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, default="resume.txt")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="txt", server_default="txt")
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class TailoredResume(Base, IdMixin):
    """Resume tailored for a specific job."""

    __tablename__ = "tailored_resumes"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True)
    source_resume_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_title_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tailored_text: Mapped[str] = mapped_column(Text, nullable=False)
    tailored_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    diff_log: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    ats_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    review_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    supervisor_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer_score: Mapped[float | None] = mapped_column(nullable=True)
    supervisor_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    violations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating", server_default="generating")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
