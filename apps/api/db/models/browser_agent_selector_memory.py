"""Selector memory for provider-scoped browser-agent fallback ordering."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class BrowserAgentSelectorMemory(Base, IdMixin):
    """Tracks selector reliability for provider/action combinations."""

    __tablename__ = "browser_agent_selector_memory"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "action_kind", "selector", name="uq_browser_agent_selector_memory"),
        Index("ix_browser_agent_selector_memory_scope", "tenant_id", "provider", "action_kind"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    selector: Mapped[str] = mapped_column(String(500), nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
