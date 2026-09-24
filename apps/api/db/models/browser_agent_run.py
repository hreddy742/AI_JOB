"""Durable run model for Browser Agent V1."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class BrowserAgentRun(Base, IdMixin, TimestampMixin):
    """Top-level browser-agent execution record."""

    __tablename__ = "browser_agent_runs"
    __table_args__ = (
        Index("ix_browser_agent_runs_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_browser_agent_runs_status", "tenant_id", "status", "created_at"),
        Index("ix_browser_agent_runs_application_created", "application_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    tailored_resume_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tailored_resumes.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", server_default="created")
    current_state: Mapped[str] = mapped_column(String(64), nullable=False, default="LANDING_PAGE", server_default="LANDING_PAGE")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", server_default="unknown")
    ats_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", server_default="unknown")
    entry_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    current_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    submit_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="human_required", server_default="human_required")
    consent_acknowledged: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    latest_perception: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    latest_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    final_review_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    feature_flag_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
