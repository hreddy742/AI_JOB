"""Dedup audit log model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import BIGINT, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DedupLog(Base):
    """Audit row for deduplication decisions."""

    __tablename__ = "dedup_log"
    __table_args__ = (
        Index("ix_dedup_log_job_id", "job_id"),
        Index("ix_dedup_log_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    canonical_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
