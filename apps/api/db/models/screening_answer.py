"""Reusable screening answers for ATS forms."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class ScreeningAnswer(Base, IdMixin):
    """Stores per-user/per-tenant answers keyed by normalized question hash."""

    __tablename__ = "screening_answers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "question_hash", "ats_type", name="uq_screening_answers_scope"),
        Index("ix_screening_answers_scope", "tenant_id", "user_id", "ats_type"),
        Index("ix_screening_answers_hash", "tenant_id", "user_id", "question_hash"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ats_type: Mapped[str] = mapped_column(String(32), nullable=False, default="generic", server_default="generic")
    job_category: Mapped[str] = mapped_column(String(100), nullable=False, default="general", server_default="general")
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    answer_source: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
