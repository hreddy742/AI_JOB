"""Resume review model."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class ResumeReview(Base, IdMixin):
    """Expert review report for a resume."""

    __tablename__ = "resume_reviews"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    review_type: Mapped[str] = mapped_column(String(30), nullable=False)

    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ats_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    impact_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    clarity_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    format_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    full_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    quick_wins: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
