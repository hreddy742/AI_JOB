"""H1B sponsor reference data."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class H1BSponsor(Base, IdMixin):
    """Aggregated sponsor statistics for H1B explorer."""

    __tablename__ = "h1b_sponsors"

    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_normalized: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    active_sponsor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    lca_count_1yr: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lca_last_1yr: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lca_last_3yr: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    approval_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    median_wage: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    median_wage_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    primary_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    approved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active_sponsor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    e_verify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    company_size: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
