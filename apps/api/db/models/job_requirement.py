"""Structured job requirement analysis model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class JobRequirement(Base, IdMixin):
    """Stores parsed requirement fields and processing state per job."""

    __tablename__ = "job_requirements"
    __table_args__ = (
        Index("ix_job_requirements_tenant_status", "tenant_id", "status"),
        Index("ix_job_requirements_job_id", "job_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    must_have_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    nice_to_have_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    tools_frameworks: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    responsibilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    min_years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seniority: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown", server_default="unknown")
    visa_sponsorship: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown", server_default="unknown")
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0, server_default="0")

    # Work authorization intelligence
    opt_allowed: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    stem_opt_allowed: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    h1b_possible: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    us_citizens_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    security_clearance_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Role intelligence
    role_family: Mapped[str] = mapped_column(String(64), nullable=False, default="other", server_default="other")
    ai_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")

    # Experience years range (min / max separately)
    experience_years_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_years_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Typed skill arrays
    programming_languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    frameworks: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    databases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    cloud_tools: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    ml_ai_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    certifications: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")

    # Salary extracted from description text
    salary_text_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)
    salary_extracted_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_extracted_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_period: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    ghost_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    extraction_provenance: Mapped[dict[str, list[dict[str, str]]]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
