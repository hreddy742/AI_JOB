"""Provider playbook model for browser-agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderPlaybook:
    provider: str
    apply_entry_selectors: tuple[str, ...]
    resume_upload_selectors: tuple[str, ...]
    upload_confirmation_selectors: tuple[str, ...]
    screening_field_selectors: tuple[str, ...]
    submit_selectors: tuple[str, ...]
    login_selectors: tuple[str, ...]
    signup_selectors: tuple[str, ...]
    validation_selectors: tuple[str, ...]
    pause_triggers: tuple[str, ...]
    login_email_selectors: tuple[str, ...] = field(default_factory=tuple)
    login_password_selectors: tuple[str, ...] = field(default_factory=tuple)
    login_submit_selectors: tuple[str, ...] = field(default_factory=tuple)
    login_success_selectors: tuple[str, ...] = field(default_factory=tuple)
    invalid_credentials_selectors: tuple[str, ...] = field(default_factory=tuple)
    signup_name_selectors: tuple[str, ...] = field(default_factory=tuple)
    signup_email_selectors: tuple[str, ...] = field(default_factory=tuple)
    signup_password_selectors: tuple[str, ...] = field(default_factory=tuple)
    signup_submit_selectors: tuple[str, ...] = field(default_factory=tuple)
    signup_success_selectors: tuple[str, ...] = field(default_factory=tuple)
    duplicate_account_selectors: tuple[str, ...] = field(default_factory=tuple)
    account_recovery_selectors: tuple[str, ...] = field(default_factory=tuple)
    review_boundary_selectors: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
