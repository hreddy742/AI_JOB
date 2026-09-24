"""Safety policies for Browser Agent V1."""

from __future__ import annotations

from browser_agent_v1.domain.enums import BrowserAgentState


LEGAL_SENSITIVE_TERMS = {
    "authorized to work",
    "work authorization",
    "sponsorship",
    "visa",
    "citizen",
    "clearance",
}


def is_sensitive_question(text: str) -> bool:
    haystack = (text or "").strip().lower()
    return any(term in haystack for term in LEGAL_SENSITIVE_TERMS)


def requires_human_pause(state: BrowserAgentState) -> bool:
    return state in {
        BrowserAgentState.CAPTCHA_REQUIRED,
        BrowserAgentState.MFA_REQUIRED,
        BrowserAgentState.MANUAL_HELP_REQUIRED,
        BrowserAgentState.READY_TO_SUBMIT,
    }


def is_terminal_state(state: BrowserAgentState) -> bool:
    return state in {BrowserAgentState.SUBMITTED, BrowserAgentState.FAILED}
