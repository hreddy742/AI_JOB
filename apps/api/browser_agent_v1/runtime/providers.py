"""Provider playbook access helpers for Browser Agent V1."""

from __future__ import annotations

from browser_agent_v1.providers import get_provider_playbook
from browser_agent_v1.runtime.capabilities import get_provider_capability


def apply_entry_selector_for_provider(ats_type: str) -> str:
    return ", ".join(get_provider_playbook(ats_type).apply_entry_selectors)


def apply_entry_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).apply_entry_selectors)


def upload_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).resume_upload_selectors)


def upload_confirmation_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).upload_confirmation_selectors)


def screening_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).screening_field_selectors)


def submit_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).submit_selectors)


def login_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).login_selectors)


def signup_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_selectors)


def login_email_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).login_email_selectors)


def login_password_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).login_password_selectors)


def login_submit_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).login_submit_selectors)


def login_success_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).login_success_selectors)


def invalid_credentials_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).invalid_credentials_selectors)


def signup_name_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_name_selectors)


def signup_email_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_email_selectors)


def signup_password_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_password_selectors)


def signup_submit_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_submit_selectors)


def signup_success_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).signup_success_selectors)


def duplicate_account_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).duplicate_account_selectors)


def account_recovery_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).account_recovery_selectors)


def review_boundary_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).review_boundary_selectors)


def validation_selectors_for_provider(ats_type: str) -> list[str]:
    return list(get_provider_playbook(ats_type).validation_selectors)


def compatibility_status_for_provider(ats_type: str) -> str:
    normalized = str(ats_type or "generic").strip().lower()
    if normalized in {"workday", "greenhouse", "lever", "icims"}:
        return "partial"
    if normalized == "generic":
        return "supported"
    return "planned"


def provider_pause_triggers(ats_type: str) -> list[str]:
    capability = get_provider_capability(ats_type)
    playbook = get_provider_playbook(ats_type)
    return list(dict.fromkeys([*capability.pause_triggers, *playbook.pause_triggers]))
