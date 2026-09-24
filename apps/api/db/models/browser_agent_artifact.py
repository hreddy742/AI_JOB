"""Artifact metadata for Browser Agent V1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class BrowserAgentArtifact(Base, IdMixin, TimestampMixin):
    """Persistent artifact metadata for one run."""

    __tablename__ = "browser_agent_artifacts"
    __table_args__ = (
        CheckConstraint("storage_path IS NOT NULL OR inline_text IS NOT NULL", name="ck_browser_agent_artifacts_payload_present"),
        Index("ix_browser_agent_artifacts_run", "run_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("browser_agent_runs.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False, default="application/octet-stream", server_default="application/octet-stream"
    )
    inline_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
