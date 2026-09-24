"""Validation extraction and recovery rules for Browser Agent V1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from browser_agent_v1.perception import PageSignals


@dataclass(slots=True)
class ValidationIssue:
    field_key: str
    message: str
    issue_type: str


def map_validation_errors(signals: PageSignals) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for message in signals.validation_errors:
        lowered = str(message or "").strip().lower()
        if not lowered:
            continue
        if "phone" in lowered:
            issues.append(ValidationIssue("phone", message, "format"))
        elif "date" in lowered:
            issues.append(ValidationIssue("date", message, "format"))
        elif "country" in lowered:
            issues.append(ValidationIssue("country", message, "selection"))
        elif "state" in lowered or "province" in lowered:
            issues.append(ValidationIssue("state", message, "selection"))
        elif "resume" in lowered or "upload" in lowered:
            issues.append(ValidationIssue("resume", message, "upload"))
        elif "required" in lowered and "checkbox" in lowered:
            issues.append(ValidationIssue("checkbox", message, "required"))
        else:
            issues.append(ValidationIssue("unknown", message, "unknown"))
    return issues


def choose_validation_recovery_actions(
    signals: PageSignals,
    profile: dict[str, Any],
    *,
    resume_file_path: str | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for issue in map_validation_errors(signals):
        if issue.field_key == "phone":
            selector = next((field.selector for field in signals.visible_fields if "phone" in f"{field.name} {field.label}".lower()), None)
            phone = str(profile.get("phone") or "").strip()
            sanitized = "".join(ch for ch in phone if ch.isdigit())
            if selector and sanitized:
                actions.append({"kind": "type", "payload": {"selector": selector, "value": sanitized}, "detail": "recover_phone"})
        elif issue.field_key == "country":
            selector = next((field.selector for field in signals.visible_fields if "country" in f"{field.name} {field.label}".lower()), None)
            location = str(profile.get("location") or "").strip()
            country = location.split(",")[-1].strip() if location else ""
            if selector and country:
                actions.append({"kind": "select", "payload": {"selector": selector, "value": country}, "detail": "recover_country"})
        elif issue.field_key == "state":
            selector = next((field.selector for field in signals.visible_fields if "state" in f"{field.name} {field.label}".lower() or "province" in f"{field.name} {field.label}".lower()), None)
            location = str(profile.get("location") or "").strip()
            state = location.split(",")[-2].strip() if location and "," in location else ""
            if selector and state:
                actions.append({"kind": "select", "payload": {"selector": selector, "value": state}, "detail": "recover_state"})
        elif issue.field_key == "resume" and resume_file_path:
            actions.append({"kind": "upload", "payload": {"selector": "input[type='file']", "path": resume_file_path}, "detail": "recover_resume_upload"})
        elif issue.field_key == "checkbox":
            selector = next((field.selector for field in signals.visible_fields if field.field_type == "checkbox" and field.required), None)
            if selector:
                actions.append({"kind": "check", "payload": {"selector": selector}, "detail": "recover_required_checkbox"})
    return actions
