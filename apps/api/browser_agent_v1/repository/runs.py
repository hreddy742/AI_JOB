"""Persistence operations for Browser Agent V1 runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from browser_agent_v1.domain.enums import BrowserAgentActor
from db.models.browser_agent_artifact import BrowserAgentArtifact
from db.models.browser_agent_event_log import BrowserAgentEventLog
from db.models.browser_agent_pause_request import BrowserAgentPauseRequest
from db.models.browser_agent_run import BrowserAgentRun
from db.models.browser_agent_state_snapshot import BrowserAgentStateSnapshot
from db.models.browser_agent_step import BrowserAgentStep


async def get_run(db: AsyncSession, run_id: UUID) -> BrowserAgentRun | None:
    """Fetch one run."""

    return (
        await db.execute(select(BrowserAgentRun).where(BrowserAgentRun.id == run_id))
    ).scalar_one_or_none()


async def get_run_for_execution(
    db: AsyncSession,
    *,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> BrowserAgentRun | None:
    """Fetch one run scoped to the expected tenant and user."""

    return (
        await db.execute(
            select(BrowserAgentRun).where(
                BrowserAgentRun.id == run_id,
                BrowserAgentRun.tenant_id == tenant_id,
                BrowserAgentRun.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def list_runs_for_user(db: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> list[BrowserAgentRun]:
    """List runs for one tenant/user."""

    result = await db.execute(
        select(BrowserAgentRun)
        .where(BrowserAgentRun.tenant_id == tenant_id, BrowserAgentRun.user_id == user_id)
        .order_by(BrowserAgentRun.created_at.desc())
    )
    return list(result.scalars().all())


async def _next_sequence(db: AsyncSession, model: Any, run_id: UUID) -> int:
    current = (
        await db.execute(select(func.max(model.sequence)).where(model.run_id == run_id))
    ).scalar_one()
    return int(current or 0) + 1


async def append_step(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    page_state: str,
    action_kind: str,
    status: str,
    selector: str | None = None,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> BrowserAgentStep:
    """Append one structured step row."""

    row = BrowserAgentStep(
        tenant_id=run.tenant_id,
        run_id=run.id,
        sequence=await _next_sequence(db, BrowserAgentStep, run.id),
        page_state=page_state,
        action_kind=action_kind,
        status=status,
        selector=selector,
        detail=detail,
        payload=payload or {},
        result=result or {},
    )
    db.add(row)
    return row


async def append_event(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    actor: BrowserAgentActor,
    event_type: str,
    message: str,
    from_state: str | None = None,
    to_state: str | None = None,
    level: str = "info",
    payload: dict[str, Any] | None = None,
) -> BrowserAgentEventLog:
    """Append one event log row."""

    row = BrowserAgentEventLog(
        tenant_id=run.tenant_id,
        run_id=run.id,
        actor=actor.value,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        level=level,
        message=message,
        payload=payload or {},
    )
    db.add(row)
    return row


async def create_snapshot(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    state: str,
    current_url: str | None,
    page_title: str | None,
    signals: dict[str, Any],
    planner_context: dict[str, Any],
) -> BrowserAgentStateSnapshot:
    """Persist a resumable state snapshot."""

    row = BrowserAgentStateSnapshot(
        tenant_id=run.tenant_id,
        run_id=run.id,
        sequence=await _next_sequence(db, BrowserAgentStateSnapshot, run.id),
        state=state,
        current_url=current_url,
        page_title=page_title,
        signals=signals,
        planner_context=planner_context,
    )
    db.add(row)
    return row


async def create_pause_request(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    reason_code: str,
    prompt: str,
    requested_data: dict[str, Any] | None = None,
) -> BrowserAgentPauseRequest:
    """Create one open pause request."""

    row = BrowserAgentPauseRequest(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        run_id=run.id,
        page_state=run.current_state,
        reason_code=reason_code,
        prompt=prompt,
        requested_data=requested_data or {},
    )
    db.add(row)
    return row


async def resolve_pause_request(
    db: AsyncSession,
    *,
    pause_request: BrowserAgentPauseRequest,
    response_data: dict[str, Any],
) -> BrowserAgentPauseRequest:
    """Resolve a pause request with user-provided data."""

    pause_request.status = "resolved"
    pause_request.response_data = response_data
    pause_request.resolved_at = datetime.now(UTC)
    return pause_request


async def list_steps(db: AsyncSession, *, run_id: UUID) -> list[BrowserAgentStep]:
    """List ordered steps for a run."""

    result = await db.execute(
        select(BrowserAgentStep).where(BrowserAgentStep.run_id == run_id).order_by(BrowserAgentStep.sequence.asc())
    )
    return list(result.scalars().all())


async def list_events(db: AsyncSession, *, run_id: UUID) -> list[BrowserAgentEventLog]:
    """List ordered events for a run."""

    result = await db.execute(
        select(BrowserAgentEventLog).where(BrowserAgentEventLog.run_id == run_id).order_by(BrowserAgentEventLog.created_at.asc())
    )
    return list(result.scalars().all())


async def list_pause_requests(db: AsyncSession, *, run_id: UUID) -> list[BrowserAgentPauseRequest]:
    """List pause requests for a run."""

    result = await db.execute(
        select(BrowserAgentPauseRequest)
        .where(BrowserAgentPauseRequest.run_id == run_id)
        .order_by(BrowserAgentPauseRequest.created_at.asc())
    )
    return list(result.scalars().all())


async def get_pause_request(db: AsyncSession, *, pause_request_id: UUID) -> BrowserAgentPauseRequest | None:
    """Fetch one pause request."""

    return (
        await db.execute(select(BrowserAgentPauseRequest).where(BrowserAgentPauseRequest.id == pause_request_id))
    ).scalar_one_or_none()


async def list_artifacts(db: AsyncSession, *, run_id: UUID) -> list[BrowserAgentArtifact]:
    """List artifacts for a run."""

    result = await db.execute(
        select(BrowserAgentArtifact).where(BrowserAgentArtifact.run_id == run_id).order_by(BrowserAgentArtifact.created_at.asc())
    )
    return list(result.scalars().all())


async def create_artifact(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    artifact_type: str,
    storage_path: str | None,
    content_type: str,
    inline_text: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> BrowserAgentArtifact:
    """Create an artifact row."""

    row = BrowserAgentArtifact(
        tenant_id=run.tenant_id,
        run_id=run.id,
        artifact_type=artifact_type,
        storage_path=storage_path,
        content_type=content_type,
        inline_text=inline_text,
        metadata_json=metadata_json or {},
    )
    db.add(row)
    return row
