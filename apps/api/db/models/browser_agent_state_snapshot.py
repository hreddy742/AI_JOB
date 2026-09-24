"""State snapshots for Browser Agent V1 resumability."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class BrowserAgentStateSnapshot(Base, IdMixin, TimestampMixin):
    """Checkpointed state snapshots for resumability."""

    __tablename__ = "browser_agent_state_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_browser_agent_state_snapshots_run_sequence"),
        Index("ix_browser_agent_state_snapshots_run_sequence", "run_id", "sequence"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("browser_agent_runs.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    current_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    page_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    planner_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
