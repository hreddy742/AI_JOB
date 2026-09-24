"""Conversation summaries for compact copilot history."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin


class ChatSummary(Base, IdMixin):
    """Summarized coverage over a range of chat messages."""

    __tablename__ = "chat_summaries"
    __table_args__ = (Index("ix_chat_summaries_session_version", "session_id", "version"),)

    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    covered_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
