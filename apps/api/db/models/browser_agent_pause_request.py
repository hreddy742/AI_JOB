"""Pause/request-response model for Browser Agent V1."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.sql import expression
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class BrowserAgentPauseRequest(Base, IdMixin, TimestampMixin):
    """Persisted pause request requiring user action."""

    __tablename__ = "browser_agent_pause_requests"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="ck_browser_agent_pause_requests_status"),
        Index("ix_browser_agent_pause_requests_run_status", "run_id", "status", "created_at"),
        Index(
            "uq_browser_agent_pause_requests_open_run",
            "run_id",
            unique=True,
            postgresql_where=expression.text("status = 'open'"),
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("browser_agent_runs.id", ondelete="CASCADE"), nullable=False)
    page_state: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", server_default="open")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    requested_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    response_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
