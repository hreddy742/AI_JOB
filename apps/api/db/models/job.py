"""Job model."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin
from db.models.enums import ExperienceLevelEnum, JobTypeEnum


class Job(Base, IdMixin):
    """Normalized job posting."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_jobs_source_source_id"),
        Index("ix_jobs_tenant_posted_at", "tenant_id", "posted_at"),
        Index("ix_jobs_company_title", "company", "title"),
        Index("ix_jobs_fingerprint", "fingerprint"),
        Index("ix_jobs_tags_gin", "tags", postgresql_using="gin"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sponsorship_score: Mapped[float] = mapped_column(nullable=False, default=0.5, server_default="0.5")
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", server_default="USD")
    job_type: Mapped[JobTypeEnum] = mapped_column(
        Enum(JobTypeEnum, name="job_type_enum"), nullable=False, default=JobTypeEnum.unknown, server_default=JobTypeEnum.unknown.value
    )
    experience_level: Mapped[ExperienceLevelEnum] = mapped_column(
        Enum(ExperienceLevelEnum, name="experience_level_enum"),
        nullable=False,
        default=ExperienceLevelEnum.unknown,
        server_default=ExperienceLevelEnum.unknown.value,
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list, server_default="{}")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    typesense_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
