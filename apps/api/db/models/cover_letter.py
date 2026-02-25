"""Cover letter model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class CoverLetter(Base, IdMixin):
    """Generated cover letter tied to a resume and optional job."""

    __tablename__ = "cover_letters"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    source_resume_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    tailored_resume_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tailored_resumes.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    job_title_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hiring_manager_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tone: Mapped[str] = mapped_column(String(30), nullable=False, default="professional", server_default="professional")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
