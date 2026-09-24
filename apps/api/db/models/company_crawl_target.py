"""Company crawl targets for ATS-driven tier-2 ingestion."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class CompanyCrawlTarget(Base, IdMixin, TimestampMixin):
    """Per-tenant company careers crawl target."""

    __tablename__ = "company_crawl_targets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "company", "careers_url", name="uq_company_crawl_target_tenant_company_url"),
        Index("ix_company_crawl_target_tenant_active", "tenant_id", "is_active"),
        Index("ix_company_crawl_target_ats", "ats_type"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    careers_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    ats_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", server_default="unknown")
    crawl_frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240, server_default="240")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
