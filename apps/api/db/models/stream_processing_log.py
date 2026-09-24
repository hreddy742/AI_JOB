"""Idempotency log for stream message processing."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class StreamProcessingLog(Base, IdMixin):
    """Tracks processed stream messages to enforce idempotency."""

    __tablename__ = "stream_processing_log"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "stream_name",
            "message_id",
            name="uq_stream_processing_log_tenant_stream_message",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    stream_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
