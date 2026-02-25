"""Outreach message model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin
from db.models.enums import OutreachStatusEnum


class OutreachMessage(Base, IdMixin):
    """Outreach draft and send lifecycle."""

    __tablename__ = "outreach_messages"

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    draft_text: Mapped[str] = mapped_column(nullable=False)
    compliance_score: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[OutreachStatusEnum] = mapped_column(
        Enum(OutreachStatusEnum, name="outreach_status_enum"),
        nullable=False,
        default=OutreachStatusEnum.draft,
        server_default=OutreachStatusEnum.draft.value,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
