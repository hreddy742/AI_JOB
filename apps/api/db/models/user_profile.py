"""User profile model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class UserProfile(Base, IdMixin):
    """User profile used for autofill and copilot context."""

    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list, server_default="{}")
    target_locations: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list, server_default="{}")
    target_salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    target_salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
