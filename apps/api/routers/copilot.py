"""Copilot API routes with SSE streaming."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.copilot_chain import generate_interview_questions, run_copilot_turn
from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.chat_session import ChatSession
from db.models.job import Job
from db.models.resume import Resume
from db.models.user_profile import UserProfile
from schemas.copilot import (
    ChatSessionCreate,
    ChatSessionResponse,
    CopilotMessageRequest,
    CopilotModeUpdate,
    InterviewQuestion,
)

router = APIRouter(prefix="/copilot", tags=["copilot"])
logger = logging.getLogger(__name__)


def _uuid(value: str) -> UUID:
    """Parse UUID and raise standardized auth error on failure."""

    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token identity") from exc


async def _get_session_for_user(db: AsyncSession, session_id: UUID, user_id: UUID, tenant_id: UUID) -> ChatSession:
    """Fetch chat session ensuring user/tenant ownership."""

    await apply_tenant_rls(db, tenant_id)
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


async def _get_profile(db: AsyncSession, user_id: UUID, tenant_id: UUID) -> UserProfile:
    """Get user profile required for copilot context."""

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id, UserProfile.tenant_id == tenant_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile is required before using Copilot")
    return profile


async def _get_optional_resume(db: AsyncSession, resume_id: UUID | None, user_id: UUID, tenant_id: UUID) -> Resume | None:
    """Load optional resume scoped to current user."""

    if resume_id is None:
        return None
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _get_optional_job(db: AsyncSession, job_id: UUID | None, tenant_id: UUID) -> Job | None:
    """Load optional job scoped to current tenant."""

    if job_id is None:
        return None
    result = await db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))
    return result.scalar_one_or_none()


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Create a new copilot chat session."""

    user_id = _uuid(token.sub)
    tenant_id = _uuid(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    session = ChatSession(
        user_id=user_id,
        tenant_id=tenant_id,
        title=payload.title,
        mode=payload.mode,
        job_id=payload.job_id,
        resume_id=payload.resume_id,
        messages=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionResponse]:
    """List chat sessions for authenticated user."""

    user_id = _uuid(token.sub)
    tenant_id = _uuid(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.tenant_id == tenant_id)
        .order_by(desc(ChatSession.updated_at), desc(ChatSession.created_at))
    )
    return [ChatSessionResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/sessions/{id}", response_model=ChatSessionResponse)
async def get_session(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Get one chat session with full history."""

    session = await _get_session_for_user(db, id, _uuid(token.sub), _uuid(token.tenant_id))
    return ChatSessionResponse.model_validate(session)


@router.delete("/sessions/{id}", status_code=status.HTTP_200_OK)
async def delete_session(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete one chat session."""

    session = await _get_session_for_user(db, id, _uuid(token.sub), _uuid(token.tenant_id))
    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


@router.post("/sessions/{id}/message")
async def send_message(
    id: UUID,
    payload: CopilotMessageRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream copilot response via SSE."""

    user_id = _uuid(token.sub)
    tenant_id = _uuid(token.tenant_id)
    session = await _get_session_for_user(db, id, user_id, tenant_id)
    profile = await _get_profile(db, user_id, tenant_id)
    resume = await _get_optional_resume(db, session.resume_id, user_id, tenant_id)
    job = await _get_optional_job(db, session.job_id, tenant_id)

    async def event_stream() -> object:
        # Send an immediate SSE comment so clients don't time out waiting for first byte.
        yield ": stream-start\n\n"
        try:
            async for chunk in run_copilot_turn(session, payload.message, profile, resume, job):
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"
        except Exception:
            logger.exception("copilot_stream_failed", extra={"session_id": str(id), "tenant_id": str(tenant_id)})
            yield "data: Copilot is temporarily unavailable. Please try again in a moment.\n\n"
        finally:
            session.updated_at = datetime.now(UTC)
            await db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions/{id}/interview-questions", response_model=list[InterviewQuestion])
async def interview_questions(
    id: UUID,
    job_id: UUID | None = Query(default=None),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewQuestion]:
    """Generate interview prep question list for session/job context."""

    user_id = _uuid(token.sub)
    tenant_id = _uuid(token.tenant_id)
    session = await _get_session_for_user(db, id, user_id, tenant_id)

    resolved_job_id = job_id or session.job_id
    if resolved_job_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id is required for interview questions")

    resume = await _get_optional_resume(db, session.resume_id, user_id, tenant_id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session must be scoped to a resume")

    job = await _get_optional_job(db, resolved_job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    questions = await generate_interview_questions(job=job, resume=resume)
    return [InterviewQuestion(**item) for item in questions]


@router.post("/sessions/{id}/mode", response_model=ChatSessionResponse)
async def switch_mode(
    id: UUID,
    payload: CopilotModeUpdate,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Switch chat session mode."""

    session = await _get_session_for_user(db, id, _uuid(token.sub), _uuid(token.tenant_id))
    session.mode = payload.mode
    session.updated_at = datetime.now(UTC)
    session.messages.append(
        {
            "role": "system",
            "content": f"Mode switched to {payload.mode}",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    await db.commit()
    await db.refresh(session)
    return ChatSessionResponse.model_validate(session)
