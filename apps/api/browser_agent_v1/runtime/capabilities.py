"""Provider capability matrix for Browser Agent V1."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider: str
    supported_states: tuple[str, ...]
    unsupported_states: tuple[str, ...]
    known_blockers: tuple[str, ...]
    pause_triggers: tuple[str, ...]
    apply_selectors: tuple[str, ...]
    upload_selectors: tuple[str, ...]


_CAPABILITIES: dict[str, ProviderCapability] = {
    "generic": ProviderCapability(
        provider="generic",
        supported_states=("JOB_DETAIL", "APPLY_ENTRY", "PROFILE_FORM", "RESUME_UPLOAD", "SCREENING_QUESTIONS", "REVIEW"),
        unsupported_states=("LOGIN", "LOGIN_REQUIRED", "SIGNUP", "SIGNUP_REQUIRED"),
        known_blockers=("custom widgets", "hidden upload flows", "multi-step signup"),
        pause_triggers=("captcha_required", "mfa_required", "manual_help_required", "validation_error_unmapped"),
        apply_selectors=("button:has-text('Apply')", "a:has-text('Apply')", "input[type='submit']"),
        upload_selectors=("input[type='file']",),
    ),
    "workday": ProviderCapability(
        provider="workday",
        supported_states=("JOB_DETAIL", "APPLY_ENTRY", "LOGIN", "LOGIN_REQUIRED", "SIGNUP", "SIGNUP_REQUIRED", "PROFILE_FORM", "RESUME_UPLOAD", "SCREENING_QUESTIONS", "REVIEW"),
        unsupported_states=("EMAIL_VERIFY_WAIT",),
        known_blockers=("account verification", "workday-specific captcha", "duplicate-account lockouts"),
        pause_triggers=("login_required", "signup_required", "email_verification_required", "captcha_required", "mfa_required"),
        apply_selectors=("a[data-automation-id='apply-button']", "button[data-automation-id='apply-button']", "a:has-text('Apply')"),
        upload_selectors=("input[data-automation-id='file-upload-input-ref']", "input[type='file']"),
    ),
    "greenhouse": ProviderCapability(
        provider="greenhouse",
        supported_states=("JOB_DETAIL", "APPLY_ENTRY", "PROFILE_FORM", "RESUME_UPLOAD", "SCREENING_QUESTIONS", "REVIEW", "READY_TO_SUBMIT"),
        unsupported_states=("LOGIN", "LOGIN_REQUIRED", "SIGNUP", "SIGNUP_REQUIRED"),
        known_blockers=("custom consent widgets", "resume parsing delay"),
        pause_triggers=("captcha_required", "manual_help_required", "validation_error_unmapped"),
        apply_selectors=("#application_button", "a#application_button", "a:has-text('Apply for this job')"),
        upload_selectors=("input[name='resume']", "input[name='cover_letter']", "input[type='file']"),
    ),
    "lever": ProviderCapability(
        provider="lever",
        supported_states=("JOB_DETAIL", "APPLY_ENTRY", "PROFILE_FORM", "RESUME_UPLOAD", "SCREENING_QUESTIONS", "REVIEW", "READY_TO_SUBMIT"),
        unsupported_states=("LOGIN", "LOGIN_REQUIRED", "SIGNUP", "SIGNUP_REQUIRED"),
        known_blockers=("custom voluntary disclosure widgets", "third-party assessment redirects"),
        pause_triggers=("captcha_required", "manual_help_required", "validation_error_unmapped"),
        apply_selectors=(".postings-btn-wrapper a", "a:has-text('Apply for this job')", "button:has-text('Apply')"),
        upload_selectors=("input[name='resume']", "input[name='coverLetter']", "input[type='file']"),
    ),
    "icims": ProviderCapability(
        provider="icims",
        supported_states=("JOB_DETAIL", "APPLY_ENTRY", "LOGIN", "LOGIN_REQUIRED", "PROFILE_FORM", "RESUME_UPLOAD", "SCREENING_QUESTIONS", "REVIEW"),
        unsupported_states=("SIGNUP", "SIGNUP_REQUIRED"),
        known_blockers=("legacy iframe flows", "location widget mismatches"),
        pause_triggers=("login_required", "captcha_required", "mfa_required", "manual_help_required"),
        apply_selectors=("a.iCIMS_ApplyOnlineButton", "button.iCIMS_ApplyOnlineButton", "a:has-text('Apply')"),
        upload_selectors=("input[type='file']", "input[name*='resume']", "input[name*='cover']"),
    ),
}


def get_provider_capability(provider: str) -> ProviderCapability:
    normalized = str(provider or "generic").strip().lower()
    return _CAPABILITIES.get(normalized, _CAPABILITIES["generic"])


def provider_capability_matrix() -> list[dict[str, object]]:
    return [asdict(item) for item in _CAPABILITIES.values()]
