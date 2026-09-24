"""Persisted state machine for Browser Agent V1."""

from __future__ import annotations

from collections.abc import Iterable

from browser_agent_v1.domain.enums import BrowserAgentState


class InvalidBrowserAgentTransition(ValueError):
    """Raised when a transition is not allowed."""


_TRANSITIONS: dict[BrowserAgentState, set[BrowserAgentState]] = {
    BrowserAgentState.LANDING_PAGE: {
        BrowserAgentState.CAREERS_LIST,
        BrowserAgentState.JOB_DETAIL,
        BrowserAgentState.APPLY_ENTRY,
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.SIGNUP,
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.CAREERS_LIST: {
        BrowserAgentState.JOB_DETAIL,
        BrowserAgentState.APPLY_ENTRY,
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.JOB_DETAIL: {
        BrowserAgentState.APPLY_ENTRY,
        BrowserAgentState.CAREERS_LIST,
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.APPLY_ENTRY: {
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.SIGNUP,
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.LOGIN: {
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.EMAIL_VERIFY_WAIT,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.SIGNUP: {
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.EMAIL_VERIFY_WAIT,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.LOGIN_REQUIRED: {
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.EMAIL_VERIFY_WAIT,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.LOGIN_SUCCESS: {
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.INVALID_CREDENTIALS: {
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.SIGNUP_REQUIRED: {
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.EMAIL_VERIFY_WAIT,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.SIGNUP_SUCCESS: {
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.ACCOUNT_ALREADY_EXISTS: {
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED: {
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.EMAIL_VERIFY_WAIT: {
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.PROFILE_FORM: {
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.RESUME_UPLOAD: {
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.SCREENING_QUESTIONS: {
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.WORK_AUTHORIZATION: {
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.REVIEW: {
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.CAPTCHA_REQUIRED: {
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.MFA_REQUIRED: {
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.MANUAL_HELP_REQUIRED: {
        BrowserAgentState.LOGIN,
        BrowserAgentState.LOGIN_REQUIRED,
        BrowserAgentState.LOGIN_SUCCESS,
        BrowserAgentState.INVALID_CREDENTIALS,
        BrowserAgentState.SIGNUP_REQUIRED,
        BrowserAgentState.SIGNUP_SUCCESS,
        BrowserAgentState.ACCOUNT_ALREADY_EXISTS,
        BrowserAgentState.ACCOUNT_RECOVERY_REQUIRED,
        BrowserAgentState.PROFILE_FORM,
        BrowserAgentState.RESUME_UPLOAD,
        BrowserAgentState.SCREENING_QUESTIONS,
        BrowserAgentState.WORK_AUTHORIZATION,
        BrowserAgentState.REVIEW,
        BrowserAgentState.READY_TO_SUBMIT,
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.READY_TO_SUBMIT: {
        BrowserAgentState.SUBMITTED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.FAILED,
    },
    BrowserAgentState.SUBMITTED: set(),
    BrowserAgentState.FAILED: set(),
}


def can_transition(current: BrowserAgentState, new: BrowserAgentState) -> bool:
    """Return whether a transition is valid."""

    if current == new:
        return True
    return new in _TRANSITIONS[current]


def assert_transition(current: BrowserAgentState, new: BrowserAgentState) -> None:
    """Raise if the transition is invalid."""

    if not can_transition(current, new):
        allowed = ", ".join(sorted(state.value for state in _TRANSITIONS[current]))
        raise InvalidBrowserAgentTransition(
            f"Invalid browser-agent transition: {current.value} -> {new.value}. Allowed: {allowed}"
        )


def path_is_valid(states: Iterable[BrowserAgentState]) -> bool:
    """Validate a sequence of states."""

    iterator = iter(states)
    try:
        current = next(iterator)
    except StopIteration:
        return True
    for new_state in iterator:
        if not can_transition(current, new_state):
            return False
        current = new_state
    return True
