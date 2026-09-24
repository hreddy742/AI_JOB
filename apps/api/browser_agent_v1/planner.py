"""Deterministic planner for Browser Agent V1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from browser_agent_v1.domain.enums import BrowserAgentState
from browser_agent_v1.domain.policies import is_sensitive_question
from browser_agent_v1.perception import PerceptionResult
from browser_agent_v1.runtime.capabilities import get_provider_capability
from browser_agent_v1.runtime.screening import choose_best_screening_match, is_low_risk_screening_question


@dataclass(slots=True)
class PlannerContext:
    entry_url: str
    current_url: str
    profile: dict[str, Any] = field(default_factory=dict)
    resume_file_path: str | None = None
    screening_answers: dict[str, str] = field(default_factory=dict)
    provider: str = "generic"
    validation_errors: list[str] = field(default_factory=list)
    employer_account_email: str | None = None
    employer_account_status: str | None = None
    employer_domain: str | None = None
    account_email: str | None = None
    account_password: str | None = None
    signup_password: str | None = None
    account_creation_confirmed: bool = False
    review_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlannerDecision:
    kind: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)


def choose_next_action(perception: PerceptionResult, context: PlannerContext) -> PlannerDecision:
    """Choose the next safe deterministic action."""

    state = perception.state
    current_url = (context.current_url or "").strip()
    entry_url = (context.entry_url or "").strip()
    capability = get_provider_capability(context.provider or perception.provider)

    if state == BrowserAgentState.LANDING_PAGE and entry_url and current_url != entry_url:
        return PlannerDecision("navigate", "Open the target entry URL.", {"url": entry_url})

    if state == BrowserAgentState.CAREERS_LIST:
        return PlannerDecision(
            "pause",
            "Careers list navigation is not deterministic enough for phase 1.",
            {"reason_code": "manual_job_selection_required"},
        )

    if state == BrowserAgentState.JOB_DETAIL:
        return PlannerDecision("click_apply", "Open the application entry point from the job detail page.")

    if state == BrowserAgentState.APPLY_ENTRY:
        return PlannerDecision("click_apply", "Open the next deterministic apply-step control.")

    if state in {BrowserAgentState.LOGIN, BrowserAgentState.LOGIN_REQUIRED, BrowserAgentState.INVALID_CREDENTIALS}:
        if not {"LOGIN", "LOGIN_REQUIRED"} & set(capability.supported_states):
            return PlannerDecision("pause", "This provider login flow is not supported yet.", {"reason_code": "login_required"})
        if "account_recovery_required" in perception.blockers:
            return PlannerDecision(
                "pause",
                "The provider is asking for account recovery or password reset.",
                {
                    "reason_code": "account_recovery_required",
                    "account_email": context.employer_account_email,
                    "account_status": context.employer_account_status,
                },
            )
        if "account_verification_required" in perception.blockers:
            return PlannerDecision(
                "pause",
                "The provider requires account verification before login can continue.",
                {
                    "reason_code": "email_verification_required",
                    "account_email": context.employer_account_email,
                    "account_status": context.employer_account_status,
                },
            )
        if "invalid_credentials" in perception.blockers or state == BrowserAgentState.INVALID_CREDENTIALS:
            return PlannerDecision(
                "pause",
                "The provider rejected the current credentials and needs a new login attempt.",
                {
                    "reason_code": "invalid_credentials",
                    "account_email": context.account_email or context.employer_account_email,
                    "account_status": context.employer_account_status,
                    "can_resume_automatically": True,
                },
            )
        if context.account_email and context.account_password:
            return PlannerDecision(
                "attempt_login",
                "Use the known account identity to continue the apply flow.",
                {
                    "account_email": context.account_email,
                    "has_password": True,
                },
            )
        return PlannerDecision(
            "pause",
            "Resume with the employer account password to continue the login flow." if (context.account_email or context.employer_account_email) else "Stored employer credentials are not configured for Browser Agent V1.",
            {
                "reason_code": "login_required",
                "account_email": context.account_email or context.employer_account_email,
                "account_status": context.employer_account_status,
                "employer_domain": context.employer_domain,
                "can_resume_automatically": True,
            },
        )

    if state in {BrowserAgentState.SIGNUP, BrowserAgentState.SIGNUP_REQUIRED}:
        if not {"SIGNUP", "SIGNUP_REQUIRED"} & set(capability.supported_states):
            return PlannerDecision("pause", "This provider signup flow is not supported yet.", {"reason_code": "signup_required"})
        if context.employer_account_email or "duplicate_account_detected" in perception.blockers:
            return PlannerDecision(
                "pause",
                "A prior employer account was detected for this provider; use login instead of creating a duplicate account.",
                {
                    "reason_code": "duplicate_account_detected",
                    "account_email": context.employer_account_email,
                    "account_status": context.employer_account_status,
                },
            )
        if "account_verification_required" in perception.blockers:
            return PlannerDecision(
                "pause",
                "The provider requires email verification before the new account can continue.",
                {
                    "reason_code": "email_verification_required",
                    "account_email": context.account_email or context.profile.get("email"),
                    "can_resume_automatically": False,
                },
            )
        if context.account_creation_confirmed and context.account_email and context.signup_password:
            return PlannerDecision(
                "attempt_signup",
                "Create the provider account with low-risk profile data before continuing.",
                {
                    "account_email": context.account_email,
                    "has_password": True,
                },
            )
        return PlannerDecision(
            "pause",
            "Account creation needs explicit confirmation and a temporary password before the agent can continue.",
            {
                "reason_code": "signup_required",
                "account_email": context.account_email or context.profile.get("email"),
                "employer_domain": context.employer_domain,
                "can_resume_automatically": True,
            },
        )

    if state == BrowserAgentState.ACCOUNT_ALREADY_EXISTS:
        return PlannerDecision(
            "pause",
            "The provider indicates this account already exists. Switch to login or recover the existing account.",
            {
                "reason_code": "duplicate_account_detected",
                "account_email": context.account_email or context.employer_account_email or context.profile.get("email"),
                "account_status": context.employer_account_status,
                "can_resume_automatically": True,
            },
        )

    if state == BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED:
        return PlannerDecision(
            "pause",
            "The provider requires account recovery before the application can continue.",
            {
                "reason_code": "account_recovery_required",
                "account_email": context.account_email or context.employer_account_email,
                "account_status": context.employer_account_status,
                "can_resume_automatically": False,
            },
        )

    if state == BrowserAgentState.EMAIL_VERIFY_WAIT:
        return PlannerDecision(
            "pause",
            "Email verification must be completed by the user.",
            {"reason_code": "email_verification_required"},
        )

    if state == BrowserAgentState.PROFILE_FORM:
        if context.validation_errors:
            return PlannerDecision("recover_validation", "Attempt a deterministic recovery for validation errors.", {"errors": context.validation_errors})
        missing = [key for key in ("first_name", "last_name", "email") if not str(context.profile.get(key) or "").strip()]
        if missing:
            return PlannerDecision(
                "pause",
                "Required profile fields are missing.",
                {"reason_code": "missing_profile_data", "missing_fields": missing},
            )
        return PlannerDecision("fill_profile", "Fill deterministic profile fields from the user profile.")

    if state == BrowserAgentState.RESUME_UPLOAD:
        if context.validation_errors:
            return PlannerDecision("recover_validation", "Retry the failed upload requirement deterministically.", {"errors": context.validation_errors})
        if not context.resume_file_path:
            return PlannerDecision(
                "pause",
                "No resume file is available for upload.",
                {"reason_code": "resume_required"},
            )
        return PlannerDecision("upload_resume", "Upload the selected resume file.", {"path": context.resume_file_path})

    if state == BrowserAgentState.SCREENING_QUESTIONS:
        if context.validation_errors:
            return PlannerDecision("recover_validation", "Recover screening validation issues before pausing.", {"errors": context.validation_errors})
        best_question = ""
        if perception.signals.visible_questions:
            best_question = perception.signals.visible_questions[0]
        elif perception.signals.labels:
            best_question = perception.signals.labels[0]
        match = choose_best_screening_match(best_question, context.screening_answers, context.profile) if best_question else None
        if match and match.sensitive:
            return PlannerDecision(
                "pause",
                "Sensitive legal or work-authorization questions require explicit user review.",
                {"reason_code": "sensitive_screening_question", "questions": [best_question], "suggested_answer": match.answer},
            )
        if match is not None:
            kind = "fill_screening_low_risk" if match.source == "profile" and not match.sensitive else "fill_screening"
            return PlannerDecision(kind, "Use reusable screening intelligence for a matching question.", {"suggested_answer": match.answer, "source": match.source})
        if best_question and is_low_risk_screening_question(best_question):
            return PlannerDecision(
                "fill_screening_low_risk",
                "Use deterministic profile-backed answer for a low-risk screening question.",
                {"question": best_question},
            )
        if not context.screening_answers:
            return PlannerDecision(
                "pause",
                "No reusable screening answers were found for this page.",
                {"reason_code": "screening_answers_required"},
            )
        sensitive_questions = [q for q in context.screening_answers if is_sensitive_question(q)]
        if sensitive_questions:
            return PlannerDecision(
                "pause",
                "Sensitive legal or work-authorization questions require explicit user review.",
                {"reason_code": "sensitive_screening_question", "questions": sensitive_questions},
            )
        return PlannerDecision("fill_screening", "Use existing screening memory for deterministic answers.")

    if state == BrowserAgentState.WORK_AUTHORIZATION:
        if context.validation_errors:
            return PlannerDecision("recover_validation", "Recover work-authorization field validation issues.", {"errors": context.validation_errors})
        work_auth = str(context.profile.get("us_work_authorization") or context.profile.get("work_authorization") or "").strip()
        if not work_auth:
            return PlannerDecision(
                "pause",
                "Work authorization data is missing or incomplete.",
                {"reason_code": "work_authorization_required"},
            )
        return PlannerDecision("fill_work_auth", "Fill explicit work-authorization answers from the profile.")

    if state == BrowserAgentState.REVIEW:
        return PlannerDecision("prepare_review", "Capture a review summary before final submission.")

    if state == BrowserAgentState.CAPTCHA_REQUIRED:
        return PlannerDecision("pause", "CAPTCHA cannot be bypassed.", {"reason_code": "captcha_required"})

    if state == BrowserAgentState.MFA_REQUIRED:
        return PlannerDecision("pause", "MFA cannot be bypassed.", {"reason_code": "mfa_required"})

    if state == BrowserAgentState.MANUAL_HELP_REQUIRED:
        return PlannerDecision("pause", "The run requires human help before continuing.", {"reason_code": "manual_help_required"})

    if state == BrowserAgentState.READY_TO_SUBMIT:
        return PlannerDecision(
            "pause",
            "Final submission requires user review and action.",
            {"reason_code": "ready_to_submit", "warnings": context.review_warnings},
        )

    if state == BrowserAgentState.SUBMITTED:
        return PlannerDecision("complete", "The target site shows a submission confirmation.")

    return PlannerDecision("fail", "Planner could not determine a safe next action.", {"reason_code": "unsupported_state"})
