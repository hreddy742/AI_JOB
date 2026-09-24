"""Deterministic page perception for Browser Agent V1."""

from __future__ import annotations

from dataclasses import dataclass, field

from browser_agent_v1.domain.enums import BrowserAgentState


@dataclass(slots=True)
class VisibleField:
    name: str
    label: str
    field_type: str
    selector: str = ""
    required: bool = False
    options: list[str] = field(default_factory=list)
    checked: bool = False


@dataclass(slots=True)
class PageSignals:
    url: str = ""
    title: str = ""
    headings: list[str] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    uploads: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    page_text: str = ""
    provider_hints: list[str] = field(default_factory=list)
    visible_fields: list[VisibleField] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    visible_questions: list[str] = field(default_factory=list)
    review_signals: list[str] = field(default_factory=list)
    submit_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PerceptionResult:
    state: BrowserAgentState
    confidence: float
    reasoning: list[str]
    blockers: list[str]
    provider: str
    signals: PageSignals


def _contains_any(values: list[str], terms: tuple[str, ...]) -> bool:
    haystack = " \n ".join(value.strip().lower() for value in values if value).strip()
    return any(term in haystack for term in terms)


def _contains_text(text: str, terms: tuple[str, ...]) -> bool:
    haystack = (text or "").strip().lower()
    return any(term in haystack for term in terms)


def classify_page(signals: PageSignals) -> PerceptionResult:
    """Classify the current page from deterministic signals."""

    reasoning: list[str] = []
    blockers = list(signals.blockers)
    provider = signals.provider_hints[0] if signals.provider_hints else "unknown"
    text = " \n ".join(
        [signals.title, *signals.headings, *signals.buttons, *signals.labels, *signals.forms, *signals.visible_questions, signals.page_text]
    ).lower()
    url = (signals.url or "").lower()

    if _contains_text(text, ("account already exists", "already have an account", "email already in use", "duplicate account", "profile already exists")):
        blockers.append("duplicate_account_detected")
    if _contains_text(text, ("forgot password", "reset your password", "recover your account", "password reset", "unlock your account")):
        blockers.append("account_recovery_required")
    if _contains_text(text, ("verify your account", "confirm your account", "activate your account", "verify your email", "check your inbox")):
        blockers.append("account_verification_required")
    if _contains_text(text, ("incorrect password", "invalid credentials", "invalid username or password", "email or password is incorrect")):
        blockers.append("invalid_credentials")

    if _contains_text(text, ("captcha", "i am not a robot", "recaptcha", "hcaptcha")):
        reasoning.append("Detected anti-bot verification language.")
        blockers.append("captcha_required")
        return PerceptionResult(BrowserAgentState.CAPTCHA_REQUIRED, 0.98, reasoning, blockers, provider, signals)

    if _contains_text(text, ("authenticator", "multi-factor", "verification code", "one-time password", "mfa")):
        reasoning.append("Detected multi-factor or verification-code language.")
        blockers.append("mfa_required")
        return PerceptionResult(BrowserAgentState.MFA_REQUIRED, 0.96, reasoning, blockers, provider, signals)

    if "account_recovery_required" in blockers:
        reasoning.append("Detected account recovery or password reset language.")
        return PerceptionResult(BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED, 0.95, reasoning, blockers, provider, signals)

    if "duplicate_account_detected" in blockers:
        reasoning.append("Detected duplicate-account or existing-account language.")
        return PerceptionResult(BrowserAgentState.ACCOUNT_ALREADY_EXISTS, 0.94, reasoning, blockers, provider, signals)

    if "invalid_credentials" in blockers:
        reasoning.append("Detected invalid credential language.")
        return PerceptionResult(BrowserAgentState.INVALID_CREDENTIALS, 0.93, reasoning, blockers, provider, signals)

    if _contains_text(text, ("application submitted", "thank you for applying", "thanks for applying")):
        reasoning.append("Detected post-submit confirmation language.")
        return PerceptionResult(BrowserAgentState.SUBMITTED, 0.97, reasoning, blockers, provider, signals)

    if signals.review_signals or _contains_text(text, ("review your application", "review application", "application review", "please review", "review and submit", "application summary")):
        reasoning.append("Detected review-step language.")
        return PerceptionResult(BrowserAgentState.REVIEW, 0.9, reasoning, blockers, provider, signals)

    if signals.submit_signals or _contains_text(text, ("submit application", "send application", "final submit", "submit your application")):
        reasoning.append("Detected final submit controls.")
        return PerceptionResult(BrowserAgentState.READY_TO_SUBMIT, 0.88, reasoning, blockers, provider, signals)

    if signals.uploads or any(field.field_type == "file" for field in signals.visible_fields):
        reasoning.append("Detected file upload controls.")
        return PerceptionResult(BrowserAgentState.RESUME_UPLOAD, 0.86, reasoning, blockers, provider, signals)

    if _contains_text(text, ("authorized to work", "work authorization", "sponsorship", "visa")):
        reasoning.append("Detected work-authorization language.")
        return PerceptionResult(BrowserAgentState.WORK_AUTHORIZATION, 0.85, reasoning, blockers, provider, signals)

    if signals.visible_questions or _contains_text(text, ("screening question", "additional question", "years of experience", "why do you", "are you willing", "desired salary")):
        reasoning.append("Detected screening-question language.")
        return PerceptionResult(BrowserAgentState.SCREENING_QUESTIONS, 0.84, reasoning, blockers, provider, signals)

    has_password = any(field.field_type == "password" for field in signals.visible_fields)
    has_form_fields = bool(signals.visible_fields)
    if has_password and _contains_text(text, ("sign in", "log in", "login")):
        reasoning.append("Detected login form fields and labels.")
        return PerceptionResult(BrowserAgentState.LOGIN_REQUIRED, 0.92, reasoning, blockers, provider, signals)

    if has_password and _contains_text(text, ("create account", "sign up", "register", "create profile")):
        reasoning.append("Detected signup form fields and labels.")
        return PerceptionResult(BrowserAgentState.SIGNUP_REQUIRED, 0.92, reasoning, blockers, provider, signals)

    if _contains_text(text, ("verify your email", "check your inbox", "email verification")):
        reasoning.append("Detected email-verification wait screen.")
        blockers.append("email_verification_required")
        return PerceptionResult(BrowserAgentState.EMAIL_VERIFY_WAIT, 0.95, reasoning, blockers, provider, signals)

    if _contains_any(signals.buttons, ("apply now", "apply", "submit application")) and _contains_text(
        text, ("job description", "about the role", "responsibilities", "qualifications")
    ):
        reasoning.append("Detected job detail page with apply controls.")
        return PerceptionResult(BrowserAgentState.JOB_DETAIL, 0.84, reasoning, blockers, provider, signals)

    if _contains_text(url, ("/jobs", "/careers", "/search-results")) and _contains_any(signals.buttons, ("apply", "view job", "learn more")):
        reasoning.append("Detected careers listing patterns from URL and buttons.")
        return PerceptionResult(BrowserAgentState.CAREERS_LIST, 0.76, reasoning, blockers, provider, signals)

    if has_form_fields or signals.forms:
        reasoning.append("Detected general form inputs without stronger ATS-specific cues.")
        return PerceptionResult(BrowserAgentState.PROFILE_FORM, 0.67, reasoning, blockers, provider, signals)

    if _contains_any(signals.buttons, ("apply", "start application")):
        reasoning.append("Detected application entry controls.")
        return PerceptionResult(BrowserAgentState.APPLY_ENTRY, 0.62, reasoning, blockers, provider, signals)

    reasoning.append("No stronger heuristic matched; treating as landing page.")
    return PerceptionResult(BrowserAgentState.LANDING_PAGE, 0.45, reasoning, blockers, provider, signals)
