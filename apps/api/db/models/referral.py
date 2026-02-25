"""Referral suggestion model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin
from db.models.enums import ReferralStatusEnum


class ReferralSuggestion(Base, IdMixin):
    """Auto-discovered referral contact suggestion."""

    __tablename__ = "referral_suggestions"
    __table_args__ = (
        Index("ix_referral_suggestions_user_job", "user_id", "job_id"),
        Index("ix_referral_suggestions_company_status", "company", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    inferred_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_pattern: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    discovery_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_verified: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    status: Mapped[ReferralStatusEnum] = mapped_column(
        Enum(ReferralStatusEnum, name="referral_status_enum"),
        nullable=False,
        default=ReferralStatusEnum.pending,
        server_default=ReferralStatusEnum.pending.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
