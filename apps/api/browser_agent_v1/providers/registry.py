"""Provider playbook registry."""

from __future__ import annotations

from browser_agent_v1.providers.base import ProviderPlaybook
from browser_agent_v1.providers.generic import PLAYBOOK as GENERIC_PLAYBOOK
from browser_agent_v1.providers.greenhouse import PLAYBOOK as GREENHOUSE_PLAYBOOK
from browser_agent_v1.providers.icims import PLAYBOOK as ICIMS_PLAYBOOK
from browser_agent_v1.providers.lever import PLAYBOOK as LEVER_PLAYBOOK
from browser_agent_v1.providers.workday import PLAYBOOK as WORKDAY_PLAYBOOK

_PLAYBOOKS: dict[str, ProviderPlaybook] = {
    "generic": GENERIC_PLAYBOOK,
    "workday": WORKDAY_PLAYBOOK,
    "greenhouse": GREENHOUSE_PLAYBOOK,
    "lever": LEVER_PLAYBOOK,
    "icims": ICIMS_PLAYBOOK,
}


def get_provider_playbook(provider: str) -> ProviderPlaybook:
    normalized = str(provider or "generic").strip().lower()
    return _PLAYBOOKS.get(normalized, _PLAYBOOKS["generic"])


def provider_playbook_catalog() -> list[dict[str, object]]:
    return [
        {
            "provider": item.provider,
            "apply_entry_selectors": item.apply_entry_selectors,
            "resume_upload_selectors": item.resume_upload_selectors,
            "upload_confirmation_selectors": item.upload_confirmation_selectors,
            "screening_field_selectors": item.screening_field_selectors,
            "submit_selectors": item.submit_selectors,
            "login_selectors": item.login_selectors,
            "signup_selectors": item.signup_selectors,
            "login_email_selectors": item.login_email_selectors,
            "login_password_selectors": item.login_password_selectors,
            "login_submit_selectors": item.login_submit_selectors,
            "login_success_selectors": item.login_success_selectors,
            "invalid_credentials_selectors": item.invalid_credentials_selectors,
            "signup_name_selectors": item.signup_name_selectors,
            "signup_email_selectors": item.signup_email_selectors,
            "signup_password_selectors": item.signup_password_selectors,
            "signup_submit_selectors": item.signup_submit_selectors,
            "signup_success_selectors": item.signup_success_selectors,
            "duplicate_account_selectors": item.duplicate_account_selectors,
            "account_recovery_selectors": item.account_recovery_selectors,
            "review_boundary_selectors": item.review_boundary_selectors,
            "validation_selectors": item.validation_selectors,
            "pause_triggers": item.pause_triggers,
            "notes": item.notes,
        }
        for item in _PLAYBOOKS.values()
    ]
