"""Core orchestration service for Browser Agent V1."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from browser_agent_v1.domain.enums import BrowserAgentActor, BrowserAgentRunStatus, BrowserAgentState
from browser_agent_v1.domain.state_machine import assert_transition
from browser_agent_v1.orchestration.checkpoints import persist_snapshot
from browser_agent_v1.perception import PageSignals, PerceptionResult, classify_page
from browser_agent_v1.planner import PlannerContext, PlannerDecision, choose_next_action
from browser_agent_v1.providers import provider_playbook_catalog
from browser_agent_v1.repository.runs import (
    append_event,
    append_step,
    create_artifact,
    create_pause_request,
    get_pause_request,
    get_run_for_execution,
    list_artifacts,
    list_events,
    list_pause_requests,
    list_runs_for_user,
    list_steps,
    resolve_pause_request,
)
from browser_agent_v1.runtime.action_executor import execute_action
from browser_agent_v1.runtime.browser_session import open_browser_session
from browser_agent_v1.runtime.file_uploads import validate_upload_path
from browser_agent_v1.runtime.observers import capture_dom_snapshot, capture_screenshot_bytes
from browser_agent_v1.runtime.page_analyzer import extract_page_signals
from browser_agent_v1.runtime.replay import build_replay_bundle
from browser_agent_v1.runtime.capabilities import provider_capability_matrix
from browser_agent_v1.runtime.providers import (
    account_recovery_selectors_for_provider,
    apply_entry_selector_for_provider,
    apply_entry_selectors_for_provider,
    compatibility_status_for_provider,
    duplicate_account_selectors_for_provider,
    invalid_credentials_selectors_for_provider,
    login_email_selectors_for_provider,
    login_password_selectors_for_provider,
    login_submit_selectors_for_provider,
    login_success_selectors_for_provider,
    review_boundary_selectors_for_provider,
    signup_email_selectors_for_provider,
    signup_name_selectors_for_provider,
    signup_password_selectors_for_provider,
    signup_submit_selectors_for_provider,
    signup_success_selectors_for_provider,
    upload_confirmation_selectors_for_provider,
    upload_selectors_for_provider,
)
from browser_agent_v1.runtime.screening import build_profile_screening_answer
from browser_agent_v1.runtime.validation import choose_validation_recovery_actions, map_validation_errors
from browser_agent_v1.storage import put_artifact_bytes
from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls
from core.observability import browser_agent_duration_seconds, browser_agent_pauses_total, browser_agent_runs_total
from core.security import TokenPayload
from db.models.application import Application
from db.models.browser_agent_pause_request import BrowserAgentPauseRequest
from db.models.browser_agent_run import BrowserAgentRun
from db.models.job import Job
from db.models.resume import Resume, TailoredResume
from db.models.user import User
from db.models.user_profile import UserProfile
from services.browser_agent_notification_service import (
    notify_browser_agent_failed,
    notify_browser_agent_paused,
    notify_browser_agent_review_required,
)
from services.browser_agent_intelligence_service import (
    cache_browser_agent_resume_secrets,
    clear_browser_agent_resume_secrets,
    employer_domain_from_url,
    get_employer_account,
    load_browser_agent_resume_secrets,
    materialize_tailored_resume_upload,
    split_browser_agent_resume_response,
    upsert_employer_account,
)
from services.screening_answer_service import get_reusable_screening_answer, upsert_screening_answer


def _serialize_perception(perception: PerceptionResult) -> dict[str, Any]:
    payload = asdict(perception)
    payload["state"] = perception.state.value
    return payload


def _serialize_plan(decision: PlannerDecision) -> dict[str, Any]:
    return {"kind": decision.kind, "reason": decision.reason, "payload": decision.payload}


def _review_summary(
    run: BrowserAgentRun,
    signals: PageSignals,
    perception: PerceptionResult,
    planner_context: PlannerContext | None = None,
    *,
    job: Job | None = None,
) -> dict[str, Any]:
    planner_context = planner_context or PlannerContext(entry_url=run.entry_url, current_url=run.current_url or run.entry_url)
    warnings = list(planner_context.review_warnings)
    if signals.validation_errors:
        warnings.append("Validation errors are still visible on the provider page.")
    if perception.blockers:
        warnings.append(f"Provider blockers detected: {', '.join(perception.blockers[:4])}.")
    return {
        "state": perception.state.value,
        "confidence": perception.confidence,
        "reasoning": perception.reasoning,
        "blockers": perception.blockers,
        "provider": str(run.ats_type or perception.provider),
        "job": {
            "id": str(getattr(run, "job_id", "") or ""),
            "title": getattr(job, "title", None),
            "company": getattr(job, "company", None),
            "location": getattr(job, "location_text", None) or getattr(job, "location_city", None),
        },
        "application": {
            "run_id": str(run.id),
            "application_id": str(getattr(run, "application_id", None)) if getattr(run, "application_id", None) else None,
            "submit_mode": str(getattr(run, "submit_mode", "human_required") or "human_required"),
        },
        "account": {
            "email": planner_context.account_email or planner_context.employer_account_email or planner_context.profile.get("email"),
            "status": planner_context.employer_account_status,
            "domain": planner_context.employer_domain,
        },
        "uploaded_resume": planner_context.resume_file_path,
        "major_answers_used": [
            {"question": question, "answer": answer}
            for question, answer in list((planner_context.screening_answers or {}).items())[:10]
        ],
        "warnings": warnings,
        "assumptions": [
            "Final submission remains user-confirmed.",
            "Any OTP, CAPTCHA, MFA, or email verification wall requires user action.",
        ],
        "url": signals.url,
        "title": signals.title,
        "headings": signals.headings[:5],
        "buttons": signals.buttons[:8],
        "validation_errors": signals.validation_errors[:10],
        "visible_questions": signals.visible_questions[:10],
    }


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _find_field_selector(signals: PageSignals, aliases: tuple[str, ...], *, field_types: tuple[str, ...] = ()) -> str | None:
    for field in signals.visible_fields:
        haystack = _normalize(f"{field.name} {field.label}")
        if any(alias in haystack for alias in aliases):
            if field_types and field.field_type not in field_types:
                continue
            return field.selector
    return None


def _warnings_from_context(
    *,
    perception: PerceptionResult,
    context: PlannerContext,
) -> list[str]:
    warnings: list[str] = []
    if perception.blockers:
        warnings.append(f"Provider blockers detected: {', '.join(perception.blockers[:4])}.")
    if context.validation_errors:
        warnings.append("Validation errors are still visible and may need user review.")
    if not context.resume_file_path:
        warnings.append("No resume file is currently attached to this run.")
    if perception.state in {BrowserAgentState.READY_TO_SUBMIT, BrowserAgentState.REVIEW}:
        warnings.append("Review the provider page before any final submit action.")
    return warnings


def _build_profile_actions(signals: PageSignals, profile: dict[str, Any]) -> list[dict[str, Any]]:
    alias_map: dict[str, tuple[str, ...]] = {
        "first_name": ("first name", "firstname", "given name", "fname"),
        "last_name": ("last name", "lastname", "surname", "lname"),
        "email": ("email", "email address"),
        "phone": ("phone", "mobile", "telephone"),
        "linkedin_url": ("linkedin",),
        "location": ("location", "city", "current location"),
    }
    actions: list[dict[str, Any]] = []
    for key, aliases in alias_map.items():
        value = str(profile.get(key) or "").strip()
        if not value:
            continue
        selector = _find_field_selector(signals, aliases)
        if selector:
            actions.append({"kind": "type", "payload": {"selector": selector, "value": value}, "detail": key})
    return actions


def _build_work_auth_actions(signals: PageSignals, profile: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    work_auth = str(profile.get("us_work_authorization") or profile.get("work_authorization") or "").strip()
    if not work_auth:
        return actions
    selector = _find_field_selector(signals, ("work authorization", "authorized", "visa", "sponsorship"))
    if selector:
        actions.append({"kind": "type", "payload": {"selector": selector, "value": work_auth}, "detail": "work_authorization"})
    return actions


def _build_screening_actions(signals: PageSignals, screening_answers: dict[str, str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for field in signals.visible_fields:
        haystack = _normalize(f"{field.name} {field.label}")
        for question, answer in screening_answers.items():
            normalized_question = _normalize(question)
            if normalized_question and (
                normalized_question in haystack or haystack in normalized_question
            ):
                actions.append({"kind": "type", "payload": {"selector": field.selector, "value": answer}, "detail": question})
                break
    return actions


def _build_low_risk_screening_actions(signals: PageSignals, profile: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for question in signals.visible_questions[:5]:
        match = build_profile_screening_answer(question, profile)
        if match is None or match.sensitive:
            continue
        for field in signals.visible_fields:
            haystack = _normalize(f"{field.name} {field.label}")
            if _normalize(question) in haystack or haystack in _normalize(question):
                kind = "select" if field.options else "type"
                actions.append({"kind": kind, "payload": {"selector": field.selector, "value": match.answer}, "detail": question})
                break
    return actions


def _selector_payload(selectors: list[str], hint: str) -> dict[str, Any]:
    ordered = [str(item) for item in selectors if str(item or "").strip()]
    return {
        "selector": ordered[0] if ordered else "",
        "selectors": ordered,
        "hint": hint,
    }


def _build_login_actions(context: PlannerContext, provider: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if context.account_email:
        actions.append(
            {
                "kind": "type",
                "payload": {
                    **_selector_payload(login_email_selectors_for_provider(provider), "login email"),
                    "value": context.account_email,
                },
                "detail": "login_email",
            }
        )
    if context.account_password:
        actions.append(
            {
                "kind": "type",
                "payload": {
                    **_selector_payload(login_password_selectors_for_provider(provider), "login password"),
                    "value": context.account_password,
                },
                "detail": "login_password",
            }
        )
    actions.append(
        {
            "kind": "click",
            "payload": _selector_payload(login_submit_selectors_for_provider(provider), "login submit"),
            "detail": "login_submit",
        }
    )
    return actions


def _build_signup_actions(context: PlannerContext, provider: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    full_name = " ".join(str(context.profile.get(key) or "").strip() for key in ("first_name", "last_name")).strip()
    if full_name:
        actions.append(
            {
                "kind": "type",
                "payload": {**_selector_payload(signup_name_selectors_for_provider(provider), "signup name"), "value": full_name},
                "detail": "signup_name",
            }
        )
    signup_email = str(context.account_email or context.profile.get("email") or "").strip()
    if signup_email:
        actions.append(
            {
                "kind": "type",
                "payload": {**_selector_payload(signup_email_selectors_for_provider(provider), "signup email"), "value": signup_email},
                "detail": "signup_email",
            }
        )
    if context.signup_password:
        actions.append(
            {
                "kind": "type",
                "payload": {
                    **_selector_payload(signup_password_selectors_for_provider(provider), "signup password"),
                    "value": context.signup_password,
                },
                "detail": "signup_password",
            }
        )
    actions.append(
        {
            "kind": "click",
            "payload": _selector_payload(signup_submit_selectors_for_provider(provider), "signup submit"),
            "detail": "signup_submit",
        }
    )
    return actions


async def _capture_artifact(db: AsyncSession, run: BrowserAgentRun, page: Any, artifact_type: str) -> None:
    screenshot = await capture_screenshot_bytes(page)
    storage_path: str | None = None
    metadata_json: dict[str, Any] = {"byte_length": len(screenshot)}
    inline_text: str | None = None
    try:
        storage_path, object_metadata = put_artifact_bytes(
            run_id=run.id,
            artifact_type=artifact_type,
            content_type="image/png",
            payload=screenshot,
        )
        metadata_json.update(object_metadata)
    except Exception:
        import base64

        inline_text = base64.b64encode(screenshot).decode("ascii")
        metadata_json["storage_fallback"] = "inline_base64"
    await create_artifact(
        db,
        run=run,
        artifact_type=artifact_type,
        storage_path=storage_path,
        content_type="image/png",
        inline_text=inline_text,
        metadata_json=metadata_json,
    )


async def _capture_dom_artifact(db: AsyncSession, run: BrowserAgentRun, page: Any, artifact_type: str) -> None:
    dom_html = await capture_dom_snapshot(page)
    storage_path: str | None = None
    metadata_json: dict[str, Any] = {"char_length": len(dom_html)}
    inline_text: str | None = None
    try:
        storage_path, object_metadata = put_artifact_bytes(
            run_id=run.id,
            artifact_type=artifact_type,
            content_type="text/html",
            payload=dom_html.encode("utf-8", errors="ignore"),
        )
        metadata_json.update(object_metadata)
    except Exception:
        inline_text = dom_html
        metadata_json["storage_fallback"] = "inline_html"
    await create_artifact(
        db,
        run=run,
        artifact_type=artifact_type,
        storage_path=storage_path,
        content_type="text/html",
        inline_text=inline_text,
        metadata_json=metadata_json,
    )


async def _transition(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    new_state: BrowserAgentState,
    actor: BrowserAgentActor,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> None:
    current = BrowserAgentState(run.current_state)
    assert_transition(current, new_state)
    run.current_state = new_state.value
    await append_event(
        db,
        run=run,
        actor=actor,
        event_type="state_transition",
        message=reason,
        from_state=current.value,
        to_state=new_state.value,
        payload=payload or {},
    )


async def _pause_run(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    prompt: str,
    reason_code: str,
    requested_data: dict[str, Any] | None = None,
    page: Any | None = None,
) -> BrowserAgentPauseRequest:
    run.status = BrowserAgentRunStatus.PAUSED.value
    browser_agent_pauses_total.labels(reason_code=reason_code).inc()
    browser_agent_runs_total.labels(
        mode=str((run.feature_flag_snapshot or {}).get("launch_mode") or "unknown"),
        status=BrowserAgentRunStatus.PAUSED.value,
    ).inc()
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.WORKER,
        event_type="run_paused",
        message=prompt,
        from_state=run.current_state,
        to_state=run.current_state,
        payload={"reason_code": reason_code, **(requested_data or {})},
    )
    pause_request = await create_pause_request(
        db,
        run=run,
        reason_code=reason_code,
        prompt=prompt,
        requested_data=requested_data,
    )
    if page is not None:
        await _capture_artifact(db, run, page, "pause_screenshot")
        await _capture_dom_artifact(db, run, page, "pause_dom_snapshot")
    if reason_code == "review_required":
        await notify_browser_agent_review_required(db, run)
    else:
        await notify_browser_agent_paused(db, run, prompt=prompt)
    return pause_request


async def _fail_run(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    error_code: str,
    error_detail: str,
    page: Any | None = None,
) -> None:
    run.status = BrowserAgentRunStatus.FAILED.value
    run.error_code = error_code
    run.error_detail = error_detail
    run.completed_at = datetime.now(UTC)
    if run.current_state != BrowserAgentState.FAILED.value:
        await _transition(
            db,
            run=run,
            new_state=BrowserAgentState.FAILED,
            actor=BrowserAgentActor.WORKER,
            reason=error_detail,
            payload={"error_code": error_code},
        )
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.WORKER,
        event_type="run_failed",
        message=error_detail,
        level="error",
        payload={"error_code": error_code},
    )
    if page is not None:
        await _capture_artifact(db, run, page, "failure_screenshot")
        await _capture_dom_artifact(db, run, page, "failure_dom_snapshot")
    await notify_browser_agent_failed(db, run)
    browser_agent_runs_total.labels(
        mode=str((run.feature_flag_snapshot or {}).get("launch_mode") or "unknown"),
        status=BrowserAgentRunStatus.FAILED.value,
    ).inc()
    if run.started_at is not None and run.completed_at is not None:
        browser_agent_duration_seconds.observe(max(0.0, (run.completed_at - run.started_at).total_seconds()))
    await clear_browser_agent_resume_secrets(run.id)


async def _record_account_state(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    context: PlannerContext,
    state: BrowserAgentState,
    source: str,
) -> None:
    account_email = str(context.account_email or context.employer_account_email or context.profile.get("email") or "").strip().lower()
    if not account_email or not context.employer_domain:
        return
    status_map = {
        BrowserAgentState.LOGIN_SUCCESS: "login_success",
        BrowserAgentState.SIGNUP_SUCCESS: "signup_success",
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS: "account_exists",
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED: "recovery_required",
        BrowserAgentState.EMAIL_VERIFY_WAIT: "verification_required",
        BrowserAgentState.INVALID_CREDENTIALS: "invalid_credentials",
        BrowserAgentState.MFA_REQUIRED: "mfa_required",
        BrowserAgentState.CAPTCHA_REQUIRED: "captcha_required",
        BrowserAgentState.LOGIN_REQUIRED: "login_required",
        BrowserAgentState.SIGNUP_REQUIRED: "signup_required",
    }
    login_status = status_map.get(state)
    if not login_status:
        return
    await upsert_employer_account(
        db,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        provider=str(run.ats_type or "generic"),
        employer_domain=context.employer_domain,
        account_email=account_email,
        login_status=login_status,
        last_login_at=datetime.now(UTC) if login_status in {"login_success", "signup_success"} else None,
        metadata_json={"source": source, "state": state.value},
    )


async def _build_context(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    signals: PageSignals,
) -> PlannerContext:
    profile = (
        await db.execute(
            select(UserProfile).where(UserProfile.tenant_id == run.tenant_id, UserProfile.user_id == run.user_id)
        )
    ).scalar_one_or_none()
    user = (
        await db.execute(select(User).where(User.id == run.user_id, User.tenant_id == run.tenant_id))
    ).scalar_one_or_none()
    resume_file_path: str | None = str((run.feature_flag_snapshot or {}).get("prepared_resume_path") or "").strip() or None
    if run.tailored_resume_id and not resume_file_path:
        tailored = (
            await db.execute(
                select(TailoredResume).where(
                    TailoredResume.tenant_id == run.tenant_id,
                    TailoredResume.user_id == run.user_id,
                    TailoredResume.id == run.tailored_resume_id,
                )
            )
        ).scalar_one_or_none()
        if tailored is not None:
            resume_file_path = materialize_tailored_resume_upload(tailored)
    elif run.resume_id and not resume_file_path:
        resume = (
            await db.execute(
                select(Resume).where(Resume.tenant_id == run.tenant_id, Resume.user_id == run.user_id, Resume.id == run.resume_id)
            )
        ).scalar_one_or_none()
        resume_file_path = getattr(resume, "file_path", None)
    else:
        resume = (
            await db.execute(
                select(Resume)
                .where(Resume.tenant_id == run.tenant_id, Resume.user_id == run.user_id, Resume.is_active.is_(True))
                .order_by(Resume.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        resume_file_path = getattr(resume, "file_path", None)

    screening_answers: dict[str, str] = {}
    candidate_questions = [
        item for item in [*signals.visible_questions, *signals.labels, *signals.headings] if "?" in item or len(item.split()) >= 4
    ][:12]
    ats_type = str(run.ats_type or "generic")
    job = None
    if hasattr(db, "execute"):
        job = (
            await db.execute(select(Job).where(Job.tenant_id == run.tenant_id, Job.id == run.job_id))
        ).scalar_one_or_none()
    job_category = str(getattr(job, "category", "general") or "general").strip().lower() or "general"
    for question in candidate_questions:
        reusable = await get_reusable_screening_answer(
            db,
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            question=question,
            ats_type=ats_type,
            job_category=job_category,
            min_confidence=0.7,
        )
        if reusable is not None:
            screening_answers[question] = reusable.answer_text

    employer_domain = employer_domain_from_url(str(getattr(job, "url", "") or run.entry_url))
    employer_account = await get_employer_account(
        db,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        provider=ats_type,
        employer_domain=employer_domain,
    )
    pause_rows = await list_pause_requests(db, run_id=run.id)
    latest_response: dict[str, Any] = {}
    for row in reversed(pause_rows):
        if str(row.status) != "resolved":
            continue
        latest_response = dict(row.response_data or {})
        if latest_response:
            break
    transient_secrets = await load_browser_agent_resume_secrets(run.id)

    profile_payload = {
        "first_name": getattr(profile, "first_name", None),
        "last_name": getattr(profile, "last_name", None),
        "email": getattr(user, "email", None),
        "phone": getattr(profile, "phone", None),
        "linkedin_url": getattr(profile, "linkedin_url", None),
        "location": getattr(profile, "current_location", None),
        "work_authorization": getattr(profile, "work_authorization", None),
        "us_work_authorization": getattr(profile, "us_work_authorization", None),
        "open_to_relocation": getattr(profile, "open_to_relocation", None),
        "willing_to_undergo_background_checks": getattr(profile, "willing_to_undergo_background_checks", None),
        "willing_to_undergo_drug_tests": getattr(profile, "willing_to_undergo_drug_tests", None),
        "notice_period": getattr(profile, "notice_period", None),
        "salary_expectation_min": getattr(profile, "salary_expectation_min", None),
        "salary_expectation_max": getattr(profile, "salary_expectation_max", None),
        "target_salary_min": getattr(profile, "target_salary_min", None),
        "target_salary_max": getattr(profile, "target_salary_max", None),
    }
    return PlannerContext(
        entry_url=run.entry_url,
        current_url=run.current_url or run.entry_url,
        profile=profile_payload,
        resume_file_path=validate_upload_path(resume_file_path),
        screening_answers=screening_answers,
        provider=run.ats_type or "generic",
        validation_errors=signals.validation_errors,
        employer_domain=employer_domain,
        employer_account_email=(employer_account.account_email if employer_account is not None else None),
        employer_account_status=(employer_account.login_status if employer_account is not None else None),
        account_email=str(
            transient_secrets.get("account_email")
            or latest_response.get("account_email")
            or (employer_account.account_email if employer_account is not None else "")
            or getattr(user, "email", "")
        ).strip()
        or None,
        account_password=str(transient_secrets.get("account_password") or "").strip() or None,
        signup_password=str(transient_secrets.get("signup_password") or "").strip() or None,
        account_creation_confirmed=bool(latest_response.get("confirm_signup") or latest_response.get("allow_signup")),
        review_warnings=_warnings_from_context(
            perception=classify_page(signals),
            context=PlannerContext(
                entry_url=run.entry_url,
                current_url=run.current_url or run.entry_url,
                profile=profile_payload,
                resume_file_path=validate_upload_path(resume_file_path),
                screening_answers=screening_answers,
                provider=run.ats_type or "generic",
                validation_errors=signals.validation_errors,
            ),
        ),
    )


async def _ensure_run_access(db: AsyncSession, token: TokenPayload, run_id: UUID) -> BrowserAgentRun:
    tenant_id = UUID(token.tenant_id)
    user_id = UUID(token.sub)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    run = (
        await db.execute(
            select(BrowserAgentRun).where(
                BrowserAgentRun.id == run_id,
                BrowserAgentRun.tenant_id == tenant_id,
                BrowserAgentRun.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser agent run not found")
    return run


async def create_run(
    db: AsyncSession,
    token: TokenPayload,
    *,
    job_id: UUID,
    application_id: UUID | None = None,
    resume_id: UUID | None = None,
    tailored_resume_id: UUID | None = None,
    consent_acknowledged: bool,
    feature_flag_snapshot: dict[str, Any] | None = None,
) -> BrowserAgentRun:
    """Create one isolated browser-agent run record."""

    tenant_id = UUID(token.tenant_id)
    user_id = UUID(token.sub)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    job = (
        await db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if application_id is not None:
        application = (
            await db.execute(
                select(Application).where(
                    Application.id == application_id,
                    Application.tenant_id == tenant_id,
                    Application.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if resume_id is not None:
        resume = (
            await db.execute(
                select(Resume).where(Resume.id == resume_id, Resume.tenant_id == tenant_id, Resume.user_id == user_id)
            )
        ).scalar_one_or_none()
        if resume is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    if tailored_resume_id is not None:
        tailored = (
            await db.execute(
                select(TailoredResume).where(
                    TailoredResume.id == tailored_resume_id,
                    TailoredResume.tenant_id == tenant_id,
                    TailoredResume.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if tailored is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored resume not found")

    run = BrowserAgentRun(
        tenant_id=tenant_id,
        user_id=user_id,
        application_id=application_id,
        job_id=job_id,
        resume_id=resume_id,
        tailored_resume_id=tailored_resume_id,
        status=BrowserAgentRunStatus.CREATED.value,
        current_state=BrowserAgentState.LANDING_PAGE.value,
        entry_url=job.url,
        current_url=job.url,
        consent_acknowledged=consent_acknowledged,
        feature_flag_snapshot=feature_flag_snapshot or {"browser_agent_v1_enabled": bool(settings.ENABLE_BROWSER_AGENT_V1)},
    )
    from services.job_coverage.ats_detection import detect_ats

    ats = await detect_ats(job.url or "", html="")
    run.provider = ats.ats_type
    run.ats_type = ats.ats_type
    db.add(run)
    browser_agent_runs_total.labels(
        mode=str((feature_flag_snapshot or {}).get("launch_mode") or "created"),
        status=BrowserAgentRunStatus.CREATED.value,
    ).inc()
    await db.flush()
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.USER,
        event_type="run_created",
        message="Browser Agent V1 run created.",
        payload={"entry_url": job.url, "consent_acknowledged": consent_acknowledged},
    )
    await db.commit()
    await db.refresh(run)
    return run


async def queue_run(db: AsyncSession, *, run: BrowserAgentRun) -> BrowserAgentRun:
    """Mark a run queued prior to worker execution."""

    run.status = BrowserAgentRunStatus.QUEUED.value
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.SYSTEM,
        event_type="run_queued",
        message="Browser Agent V1 run queued.",
    )
    await db.commit()
    await db.refresh(run)
    return run


async def get_run_for_user(db: AsyncSession, token: TokenPayload, run_id: UUID) -> BrowserAgentRun:
    """Fetch one run for the current user."""

    return await _ensure_run_access(db, token, run_id)


async def list_runs(db: AsyncSession, token: TokenPayload) -> list[BrowserAgentRun]:
    """List browser-agent runs for the current user."""

    tenant_id = UUID(token.tenant_id)
    user_id = UUID(token.sub)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    return await list_runs_for_user(db, tenant_id=tenant_id, user_id=user_id)


async def cancel_run(db: AsyncSession, token: TokenPayload, run_id: UUID) -> BrowserAgentRun:
    """Cancel a run."""

    run = await _ensure_run_access(db, token, run_id)
    run.status = BrowserAgentRunStatus.CANCELLED.value
    run.cancelled_at = datetime.now(UTC)
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.USER,
        event_type="run_cancelled",
        message="Browser Agent V1 run cancelled by user.",
    )
    await db.commit()
    await db.refresh(run)
    return run


async def submit_pause_response(
    db: AsyncSession,
    token: TokenPayload,
    *,
    run_id: UUID,
    pause_request_id: UUID,
    response_data: dict[str, Any],
) -> BrowserAgentPauseRequest:
    """Resolve one pause request with user input."""

    run = await _ensure_run_access(db, token, run_id)
    pause_request = await get_pause_request(db, pause_request_id=pause_request_id)
    if pause_request is None or pause_request.run_id != run.id or pause_request.user_id != run.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pause request not found")
    durable_response, transient_secrets = split_browser_agent_resume_response(response_data)
    await resolve_pause_request(db, pause_request=pause_request, response_data=durable_response)
    await cache_browser_agent_resume_secrets(run.id, transient_secrets)
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.USER,
        event_type="pause_response_submitted",
        message="User submitted data for a paused run.",
        payload={"pause_request_id": str(pause_request_id)},
    )
    response_questions = durable_response.get("screening_answers")
    if isinstance(response_questions, list):
        job = (
            await db.execute(select(Job).where(Job.tenant_id == run.tenant_id, Job.id == run.job_id))
        ).scalar_one_or_none()
        job_category = str(getattr(job, "category", "general") or "general").strip().lower() or "general"
        for item in response_questions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if not question or not answer:
                continue
            await upsert_screening_answer(
                db,
                tenant_id=run.tenant_id,
                user_id=run.user_id,
                question=question,
                answer=answer,
                ats_type=str(run.ats_type or "generic"),
                job_category=job_category,
                confidence=float(item.get("confidence") or 0.75),
                mark_success=False,
                answer_source="pause_response",
            )
    account_email = str(durable_response.get("account_email") or transient_secrets.get("account_email") or "").strip().lower()
    if account_email:
        employer_domain = employer_domain_from_url(run.entry_url)
        login_status = "known"
        metadata_json: dict[str, Any] = {"source": "pause_response"}
        if pause_request.reason_code in {"email_verification_required", "verification_required"}:
            login_status = "verification_required"
        elif pause_request.reason_code == "duplicate_account_detected":
            login_status = "account_exists"
        elif pause_request.reason_code == "account_recovery_required":
            login_status = "recovery_required"
        elif durable_response.get("confirm_signup") or durable_response.get("allow_signup"):
            login_status = "signup_confirmed"
        if durable_response.get("allow_login"):
            metadata_json["allow_login"] = True
        if durable_response.get("confirm_signup") or durable_response.get("allow_signup"):
            metadata_json["allow_signup"] = True
        await upsert_employer_account(
            db,
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            provider=str(run.ats_type or "generic"),
            employer_domain=employer_domain,
            account_email=account_email,
            login_status=login_status,
            metadata_json=metadata_json,
        )
    await db.commit()
    await db.refresh(pause_request)
    return pause_request


async def resume_run(db: AsyncSession, token: TokenPayload, run_id: UUID) -> BrowserAgentRun:
    """Resume a paused run."""

    run = await _ensure_run_access(db, token, run_id)
    run.status = BrowserAgentRunStatus.QUEUED.value
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.USER,
        event_type="run_resumed",
        message="Browser Agent V1 run resumed by user.",
    )
    await db.commit()
    await db.refresh(run)
    return run


async def get_run_steps(db: AsyncSession, token: TokenPayload, run_id: UUID) -> list[Any]:
    run = await _ensure_run_access(db, token, run_id)
    return await list_steps(db, run_id=run.id)


async def get_run_events(db: AsyncSession, token: TokenPayload, run_id: UUID) -> list[Any]:
    run = await _ensure_run_access(db, token, run_id)
    return await list_events(db, run_id=run.id)


async def get_run_pause_requests(db: AsyncSession, token: TokenPayload, run_id: UUID) -> list[Any]:
    run = await _ensure_run_access(db, token, run_id)
    return await list_pause_requests(db, run_id=run.id)


async def get_run_artifacts(db: AsyncSession, token: TokenPayload, run_id: UUID) -> list[Any]:
    run = await _ensure_run_access(db, token, run_id)
    return await list_artifacts(db, run_id=run.id)


async def get_review_summary(db: AsyncSession, token: TokenPayload, run_id: UUID) -> dict[str, Any]:
    run = await _ensure_run_access(db, token, run_id)
    return dict(run.final_review_summary or {})


async def get_replay_bundle(db: AsyncSession, token: TokenPayload, run_id: UUID) -> dict[str, Any]:
    run = await _ensure_run_access(db, token, run_id)
    steps = await list_steps(db, run_id=run.id)
    events = await list_events(db, run_id=run.id)
    artifacts = await list_artifacts(db, run_id=run.id)
    pause_requests = await list_pause_requests(db, run_id=run.id)
    return build_replay_bundle(run=run, steps=steps, events=events, artifacts=artifacts, pause_requests=pause_requests)


async def execute_run_by_id(
    db: AsyncSession,
    *,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    session_factory=open_browser_session,
) -> BrowserAgentRun:
    """Execute a queued browser-agent run."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    run = await get_run_for_execution(db, run_id=run_id, tenant_id=tenant_id, user_id=user_id)
    if run is None:
        raise ValueError("Browser-agent run not found")
    if run.status == BrowserAgentRunStatus.CANCELLED.value:
        return run
    job = None
    if hasattr(db, "execute"):
        job = (
            await db.execute(select(Job).where(Job.tenant_id == run.tenant_id, Job.id == run.job_id))
        ).scalar_one_or_none()

    run.status = BrowserAgentRunStatus.RUNNING.value
    run.started_at = run.started_at or datetime.now(UTC)
    run.last_heartbeat_at = datetime.now(UTC)
    await append_event(
        db,
        run=run,
        actor=BrowserAgentActor.WORKER,
        event_type="run_started",
        message="Browser Agent V1 worker started.",
    )
    await db.commit()

    try:
        async with session_factory(headless=bool(settings.BROWSER_AGENT_V1_HEADLESS)) as session:
            page = session.page
            await page.goto(run.current_url or run.entry_url, wait_until="domcontentloaded", timeout=45000)
            await _capture_dom_artifact(db, run, page, "page_load_dom_snapshot")
            for _ in range(int(settings.BROWSER_AGENT_V1_MAX_STEPS_PER_RUN)):
                run.last_heartbeat_at = datetime.now(UTC)
                current_url = str(getattr(page, "url", "") or run.current_url or run.entry_url)
                run.current_url = current_url
                title = await page.title()
                signals = await extract_page_signals(page, url=current_url, title=title)
                perception = classify_page(signals)
                run.latest_perception = _serialize_perception(perception)
                if run.current_state != perception.state.value:
                    await _transition(
                        db,
                        run=run,
                        new_state=perception.state,
                        actor=BrowserAgentActor.WORKER,
                        reason="Perception updated the current page state.",
                        payload={"confidence": perception.confidence},
                    )
                planner_context = await _build_context(db, run=run, signals=signals)
                decision = choose_next_action(perception, planner_context)
                run.latest_plan = _serialize_plan(decision)
                run.final_review_summary = _review_summary(run, signals, perception, planner_context, job=job)
                await persist_snapshot(
                    db,
                    run=run,
                    page_title=title,
                    signals=signals,
                    planner_context=asdict(planner_context),
                )
                if signals.validation_errors:
                    await _capture_dom_artifact(db, run, page, "validation_dom_snapshot")
                await db.commit()

                if decision.kind == "pause":
                    await _record_account_state(db, run=run, context=planner_context, state=perception.state, source="pause")
                    await _pause_run(
                        db,
                        run=run,
                        prompt=decision.reason,
                        reason_code=str(decision.payload.get("reason_code") or "manual_help_required"),
                        requested_data=decision.payload,
                        page=page,
                    )
                    await db.commit()
                    await db.refresh(run)
                    return run

                if decision.kind == "complete":
                    run.status = BrowserAgentRunStatus.COMPLETED.value
                    run.completed_at = datetime.now(UTC)
                    await append_event(
                        db,
                        run=run,
                        actor=BrowserAgentActor.WORKER,
                        event_type="run_completed",
                        message=decision.reason,
                    )
                    await db.commit()
                    await db.refresh(run)
                    browser_agent_runs_total.labels(
                        mode=str((run.feature_flag_snapshot or {}).get("launch_mode") or "unknown"),
                        status=BrowserAgentRunStatus.COMPLETED.value,
                    ).inc()
                    if run.started_at is not None and run.completed_at is not None:
                        browser_agent_duration_seconds.observe(max(0.0, (run.completed_at - run.started_at).total_seconds()))
                    await clear_browser_agent_resume_secrets(run.id)
                    return run

                if decision.kind == "fail":
                    await _fail_run(
                        db,
                        run=run,
                        error_code=str(decision.payload.get("reason_code") or "unsupported_state"),
                        error_detail=decision.reason,
                        page=page,
                    )
                    await db.commit()
                    await db.refresh(run)
                    return run

                if decision.kind == "prepare_review":
                    await _pause_run(
                        db,
                        run=run,
                        prompt="Review the captured application summary before continuing.",
                        reason_code="review_required",
                        requested_data=run.final_review_summary,
                        page=page,
                    )
                    await db.commit()
                    await db.refresh(run)
                    return run

                actions: list[dict[str, Any]] = []
                if decision.kind == "navigate":
                    actions = [{"kind": "navigate", "payload": decision.payload, "detail": "navigate"}]
                elif decision.kind == "click_apply":
                    actions = [
                        {
                            "kind": "click",
                            "payload": {
                                "selector": apply_entry_selector_for_provider(run.ats_type),
                                "selectors": apply_entry_selectors_for_provider(run.ats_type),
                                "hint": "apply",
                            },
                            "detail": "click_apply",
                        }
                    ]
                elif decision.kind == "fill_profile":
                    actions = _build_profile_actions(signals, planner_context.profile)
                elif decision.kind == "attempt_login":
                    actions = _build_login_actions(planner_context, str(run.ats_type or "generic"))
                elif decision.kind == "attempt_signup":
                    actions = _build_signup_actions(planner_context, str(run.ats_type or "generic"))
                elif decision.kind == "upload_resume":
                    actions = [
                        {
                            "kind": "upload",
                            "payload": {
                                "selector": upload_selectors_for_provider(run.ats_type)[0],
                                "selectors": upload_selectors_for_provider(run.ats_type),
                                "path": planner_context.resume_file_path,
                                "hint": "resume upload",
                                "confirmation_selectors": upload_confirmation_selectors_for_provider(run.ats_type),
                                "confirmation_timeout_ms": int(settings.BROWSER_AGENT_V1_UPLOAD_CONFIRMATION_TIMEOUT_MS),
                            },
                            "detail": "resume_upload",
                        }
                    ]
                elif decision.kind == "fill_work_auth":
                    actions = _build_work_auth_actions(signals, planner_context.profile)
                elif decision.kind == "fill_screening":
                    actions = _build_screening_actions(signals, planner_context.screening_answers)
                elif decision.kind == "fill_screening_low_risk":
                    actions = _build_low_risk_screening_actions(signals, planner_context.profile)
                elif decision.kind == "recover_validation":
                    actions = choose_validation_recovery_actions(
                        signals,
                        planner_context.profile,
                        resume_file_path=planner_context.resume_file_path,
                    )

                if not actions:
                    await _pause_run(
                        db,
                        run=run,
                        prompt="No deterministic executor actions were generated for the current state.",
                        reason_code="manual_help_required",
                        requested_data={"state": run.current_state, "decision": _serialize_plan(decision)},
                        page=page,
                    )
                    await db.commit()
                    await db.refresh(run)
                    return run

                for action in actions:
                    result = await execute_action(
                        page,
                        action["kind"],
                        action["payload"],
                        db=db,
                        tenant_id=run.tenant_id,
                        provider=str(run.ats_type or "generic"),
                    )
                    await append_step(
                        db,
                        run=run,
                        page_state=run.current_state,
                        action_kind=action["kind"],
                        status="completed" if result.get("ok", True) else "failed",
                        selector=action["payload"].get("selector"),
                        detail=str(action.get("detail") or ""),
                        payload=action["payload"],
                        result=result,
                    )
                    await append_event(
                        db,
                        run=run,
                        actor=BrowserAgentActor.WORKER,
                        event_type="selector_fallback_used" if result.get("fallback_used") else "action_executed",
                        message="Selector fallback was used for a browser action." if result.get("fallback_used") else "Browser action completed.",
                        payload={"action_kind": action["kind"], "attempts": result.get("attempts") or []},
                    )
                    if not result.get("ok", True):
                        await append_event(
                            db,
                            run=run,
                            actor=BrowserAgentActor.WORKER,
                            event_type="selector_failed",
                            message="All selector candidates failed for a browser action.",
                            level="warning",
                            payload={"action_kind": action["kind"], "attempts": result.get("attempts") or []},
                        )
                        await _pause_run(
                            db,
                            run=run,
                            prompt="A deterministic browser action failed and needs review.",
                            reason_code="action_failed",
                            requested_data={"action": action, "result": result},
                            page=page,
                        )
                        await db.commit()
                        await db.refresh(run)
                        return run
                title = await page.title()
                post_action_signals = await extract_page_signals(page, url=str(getattr(page, "url", "") or run.current_url or run.entry_url), title=title)
                post_action_perception = classify_page(post_action_signals)
                if decision.kind in {"attempt_login", "attempt_signup"}:
                    transition_state: BrowserAgentState | None = None
                    if post_action_perception.state in {
                        BrowserAgentState.PROFILE_FORM,
                        BrowserAgentState.RESUME_UPLOAD,
                        BrowserAgentState.SCREENING_QUESTIONS,
                        BrowserAgentState.WORK_AUTHORIZATION,
                        BrowserAgentState.REVIEW,
                        BrowserAgentState.READY_TO_SUBMIT,
                    }:
                        transition_state = (
                            BrowserAgentState.LOGIN_SUCCESS if decision.kind == "attempt_login" else BrowserAgentState.SIGNUP_SUCCESS
                        )
                    elif post_action_perception.state in {
                        BrowserAgentState.INVALID_CREDENTIALS,
                        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
                        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
                        BrowserAgentState.EMAIL_VERIFY_WAIT,
                        BrowserAgentState.MFA_REQUIRED,
                        BrowserAgentState.CAPTCHA_REQUIRED,
                    }:
                        transition_state = post_action_perception.state
                    if transition_state is not None and run.current_state != transition_state.value:
                        await _transition(
                            db,
                            run=run,
                            new_state=transition_state,
                            actor=BrowserAgentActor.WORKER,
                            reason="Account-flow outcome classified after deterministic execution.",
                            payload={"decision_kind": decision.kind},
                        )
                    if transition_state is not None:
                        await _record_account_state(db, run=run, context=planner_context, state=transition_state, source="post_action")
                    if transition_state in {BrowserAgentState.LOGIN_SUCCESS, BrowserAgentState.SIGNUP_SUCCESS}:
                        await clear_browser_agent_resume_secrets(run.id)
                if post_action_signals.submit_signals:
                    await _capture_dom_artifact(db, run, page, "submission_boundary_dom_snapshot")
                elif review_boundary_selectors_for_provider(str(run.ats_type or "generic")):
                    try:
                        for selector in review_boundary_selectors_for_provider(str(run.ats_type or "generic")):
                            if await page.locator(selector).first.is_visible(timeout=750):
                                await _capture_dom_artifact(db, run, page, "submission_boundary_dom_snapshot")
                                break
                    except Exception:
                        pass
                recovery_issues = map_validation_errors(post_action_signals)
                if recovery_issues:
                    await append_event(
                        db,
                        run=run,
                        actor=BrowserAgentActor.WORKER,
                        event_type="validation_recovery_attempt",
                        message="Validation errors remained after a deterministic action batch.",
                        level="warning",
                        payload={"issues": [issue.__dict__ for issue in recovery_issues]},
                    )
                await db.commit()

        await _fail_run(
            db,
            run=run,
            error_code="step_limit_exceeded",
            error_detail="Browser Agent V1 reached the configured step limit without a safe terminal outcome.",
        )
        await db.commit()
        await db.refresh(run)
        return run
    except Exception as exc:
        await _fail_run(
            db,
            run=run,
            error_code="execution_exception",
            error_detail=str(exc),
        )
        await db.commit()
        await db.refresh(run)
        return run


def compatibility_catalog() -> list[dict[str, Any]]:
    """Return supported providers and safety notes."""

    matrix = []
    playbooks = {str(item["provider"]): item for item in provider_playbook_catalog()}
    for item in provider_capability_matrix():
        provider = str(item["provider"])
        matrix.append(
            {
                **item,
                "playbook": playbooks.get(provider, {}),
                "status": compatibility_status_for_provider(provider),
                "notes": "Deterministic provider capability matrix for rollout and operator use.",
            }
        )
    return matrix
