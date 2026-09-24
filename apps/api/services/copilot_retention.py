"""Copilot retention helpers: rolling window + summaries + caps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls
from db.models.chat_message import ChatMessage
from db.models.chat_summary import ChatSummary
from db.models.chat_session import ChatSession


def _summarize_messages(messages: list[ChatMessage], max_chars: int = 2000) -> str:
    """Deterministic lightweight summary for old turns."""

    if not messages:
        return ""
    lines: list[str] = []
    for msg in messages:
        role = msg.role.upper()
        content = (msg.content or "").strip().replace("\n", " ")
        if not content:
            continue
        lines.append(f"{role}: {content[:220]}")
        if sum(len(item) for item in lines) > max_chars:
            break
    return "\n".join(lines)[:max_chars]


async def persist_recent_turns(
    db: AsyncSession,
    session: ChatSession,
    tenant_id: UUID,
) -> None:
    """Persist latest turn messages from denormalized session buffer."""

    await apply_tenant_rls(db, tenant_id)
    tail = session.messages[-2:] if session.messages else []
    for msg in tail:
        role = str(msg.get("role", "user"))[:16]
        content = str(msg.get("content", ""))
        if not content:
            continue
        db.add(
            ChatMessage(
                session_id=session.id,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                role=role,
                content=content,
            )
        )
    await db.flush()


async def apply_session_retention(
    db: AsyncSession,
    session: ChatSession,
    tenant_id: UUID,
) -> None:
    """Apply rolling raw window and summarize older raw messages."""

    await apply_tenant_rls(db, tenant_id)
    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.tenant_id == session.tenant_id)
            .order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()

    raw_cap = max(int(settings.COPILOT_RAW_MESSAGES_CAP), 20)
    if len(rows) <= raw_cap:
        # Keep denormalized compatibility field bounded as well.
        window = max(int(settings.COPILOT_RAW_TURNS_WINDOW) * 2, 10)
        session.messages = (session.messages or [])[-window:]
        return

    overflow = rows[: len(rows) - raw_cap]
    summary_text = _summarize_messages(overflow)
    if summary_text:
        latest_ver = (
            await db.execute(
                select(func.max(ChatSummary.version)).where(
                    ChatSummary.session_id == session.id,
                    ChatSummary.tenant_id == session.tenant_id,
                )
            )
        ).scalar_one_or_none()
        db.add(
            ChatSummary(
                session_id=session.id,
                tenant_id=session.tenant_id,
                version=int(latest_ver or 0) + 1,
                summary_text=summary_text,
                covered_messages=len(overflow),
            )
        )

    overflow_ids = [row.id for row in overflow]
    if overflow_ids:
        await db.execute(delete(ChatMessage).where(ChatMessage.id.in_(overflow_ids)))

    window = max(int(settings.COPILOT_RAW_TURNS_WINDOW) * 2, 10)
    session.messages = (session.messages or [])[-window:]


async def prune_inactive_sessions(db: AsyncSession, tenant_id: UUID) -> int:
    """Prune raw chat messages for inactive sessions past retention horizon."""

    await apply_tenant_rls(db, tenant_id)
    cutoff = datetime.now(UTC) - timedelta(days=max(int(settings.COPILOT_INACTIVE_RETENTION_DAYS), 1))
    stale_ids = (
        await db.execute(
            select(ChatSession.id).where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.updated_at < cutoff,
            )
        )
    ).scalars().all()
    if not stale_ids:
        return 0
    result = await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(stale_ids)))
    return int(result.rowcount or 0)
