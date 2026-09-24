"""OPT tracker settings and state."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class OptTracker(Base, IdMixin):
    """Per-user OPT tracker configuration."""

    __tablename__ = "opt_tracker"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opt_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opt_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stem_opt_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    stem_opt_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    stem_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    h1b_filed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    focused_on_h1b_companies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    urgency_level: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", server_default="normal")
    last_alert_sent: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
