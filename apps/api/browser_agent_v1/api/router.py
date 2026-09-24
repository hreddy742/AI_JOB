"""Isolated API routes for Browser Agent V1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from browser_agent_v1.api.schemas import (
    BrowserAgentArtifactResponse,
    BrowserAgentCompatibilityResponse,
    BrowserAgentEventResponse,
    BrowserAgentPauseRequestResponse,
    BrowserAgentPauseResponseRequest,
    BrowserAgentReplayBundleResponse,
    BrowserAgentReviewSummaryResponse,
    BrowserAgentRunCreateRequest,
    BrowserAgentRunResponse,
    BrowserAgentStepResponse,
)
from browser_agent_v1.orchestration.scheduler import enqueue_run
from browser_agent_v1.orchestration.service import (
    cancel_run,
    compatibility_catalog,
    create_run,
    get_review_summary,
    get_replay_bundle,
    get_run_artifacts,
    get_run_events,
    get_run_for_user,
    get_run_pause_requests,
    get_run_steps,
    list_runs,
    queue_run,
    resume_run,
    submit_pause_response,
)
from core.arq_queues import QUEUE_BROWSER_AGENT_V1
from core.config import settings
from core.dependencies import get_current_token, get_db
from core.security import TokenPayload

router = APIRouter(prefix="/browser-agent/v1", tags=["browser-agent-v1"])


def _ensure_enabled() -> None:
    if not settings.ENABLE_BROWSER_AGENT_V1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser Agent V1 is disabled")


@router.post("/runs", response_model=BrowserAgentRunResponse, status_code=201)
async def create_run_endpoint(
    payload: BrowserAgentRunCreateRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentRunResponse:
    _ensure_enabled()
    run = await create_run(
        db,
        token,
        job_id=payload.job_id,
        application_id=payload.application_id,
        resume_id=payload.resume_id,
        tailored_resume_id=payload.tailored_resume_id,
        consent_acknowledged=payload.consent_acknowledged,
    )
    run = await queue_run(db, run=run)
    await enqueue_run(
        str(run.id),
        tenant_id=str(run.tenant_id),
        user_id=str(run.user_id),
        queue_name=QUEUE_BROWSER_AGENT_V1,
    )
    return BrowserAgentRunResponse.model_validate(run)


@router.get("/runs", response_model=list[BrowserAgentRunResponse])
async def list_runs_endpoint(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[BrowserAgentRunResponse]:
    _ensure_enabled()
    rows = await list_runs(db, token)
    return [BrowserAgentRunResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}", response_model=BrowserAgentRunResponse)
async def get_run_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentRunResponse:
    _ensure_enabled()
    run = await get_run_for_user(db, token, run_id)
    return BrowserAgentRunResponse.model_validate(run)


@router.get("/runs/{run_id}/steps", response_model=list[BrowserAgentStepResponse])
async def get_steps_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[BrowserAgentStepResponse]:
    _ensure_enabled()
    rows = await get_run_steps(db, token, run_id)
    return [BrowserAgentStepResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/events", response_model=list[BrowserAgentEventResponse])
async def get_events_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[BrowserAgentEventResponse]:
    _ensure_enabled()
    rows = await get_run_events(db, token, run_id)
    return [BrowserAgentEventResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/pause-requests", response_model=list[BrowserAgentPauseRequestResponse])
async def get_pause_requests_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[BrowserAgentPauseRequestResponse]:
    _ensure_enabled()
    rows = await get_run_pause_requests(db, token, run_id)
    return [BrowserAgentPauseRequestResponse.model_validate(row) for row in rows]


@router.post("/runs/{run_id}/pause-requests/{pause_request_id}/respond", response_model=BrowserAgentPauseRequestResponse)
async def respond_pause_request_endpoint(
    run_id: UUID,
    pause_request_id: UUID,
    payload: BrowserAgentPauseResponseRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentPauseRequestResponse:
    _ensure_enabled()
    row = await submit_pause_response(
        db,
        token,
        run_id=run_id,
        pause_request_id=pause_request_id,
        response_data=payload.response_data,
    )
    return BrowserAgentPauseRequestResponse.model_validate(row)


@router.post("/runs/{run_id}/resume", response_model=BrowserAgentRunResponse)
async def resume_run_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentRunResponse:
    _ensure_enabled()
    run = await resume_run(db, token, run_id)
    await enqueue_run(
        str(run.id),
        tenant_id=str(run.tenant_id),
        user_id=str(run.user_id),
        queue_name=QUEUE_BROWSER_AGENT_V1,
    )
    return BrowserAgentRunResponse.model_validate(run)


@router.post("/runs/{run_id}/cancel", response_model=BrowserAgentRunResponse)
async def cancel_run_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentRunResponse:
    _ensure_enabled()
    run = await cancel_run(db, token, run_id)
    return BrowserAgentRunResponse.model_validate(run)


@router.get("/runs/{run_id}/artifacts", response_model=list[BrowserAgentArtifactResponse])
async def artifacts_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[BrowserAgentArtifactResponse]:
    _ensure_enabled()
    rows = await get_run_artifacts(db, token, run_id)
    return [BrowserAgentArtifactResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/review-summary", response_model=BrowserAgentReviewSummaryResponse)
async def review_summary_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentReviewSummaryResponse:
    _ensure_enabled()
    summary = await get_review_summary(db, token, run_id)
    return BrowserAgentReviewSummaryResponse(summary=summary)


@router.get("/runs/{run_id}/replay-bundle", response_model=BrowserAgentReplayBundleResponse)
async def replay_bundle_endpoint(
    run_id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> BrowserAgentReplayBundleResponse:
    _ensure_enabled()
    bundle = await get_replay_bundle(db, token, run_id)
    return BrowserAgentReplayBundleResponse(bundle=bundle)


@router.get("/catalog/compatibility", response_model=BrowserAgentCompatibilityResponse)
async def compatibility_endpoint(
    token: TokenPayload = Depends(get_current_token),
) -> BrowserAgentCompatibilityResponse:
    _ensure_enabled()
    return BrowserAgentCompatibilityResponse(items=compatibility_catalog())
