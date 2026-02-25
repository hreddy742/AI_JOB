"""Tenant model."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin
from db.models.enums import PlanEnum


class Tenant(Base, IdMixin):
    """Tenant entity used for multi-tenant isolation."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[PlanEnum] = mapped_column(
        Enum(PlanEnum, name="plan_enum"), nullable=False, default=PlanEnum.free, server_default=PlanEnum.free.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
