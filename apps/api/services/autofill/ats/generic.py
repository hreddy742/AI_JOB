"""Generic ATS autofill adapter with deterministic field handling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.autofill.actions import click, select_option, type_text, wait_for
from services.autofill.ats.base import ScreeningLookup

SAFE_FIELD_LABELS: dict[str, list[str]] = {
    "first_name": ["first name", "first_name", "fname", "given name"],
    "last_name": ["last name", "last_name", "lname", "family name", "surname"],
    "email": ["email", "email address", "e-mail"],
    "phone": ["phone", "telephone", "mobile", "cell"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin profile"],
    "location": ["city", "location", "current location", "current city"],
    "us_work_authorization": ["work authorization", "authorized to work", "work status"],
    "requires_us_sponsorship": ["require sponsorship", "need sponsorship", "visa sponsorship"],
    "legally_allowed_to_work_in_us": ["legally allowed to work", "authorized to work in the u s", "work in the us"],
    "remote_work_preference": ["remote preference", "remote work", "work mode"],
    "in_person_work_preference": ["in person preference", "on site preference", "onsite preference"],
    "open_to_relocation": ["open to relocation", "willing to relocate", "relocation"],
    "willing_to_complete_assessments": ["complete assessments", "assessment", "online assessment"],
    "willing_to_undergo_background_checks": ["background check", "background screening"],
    "willing_to_undergo_drug_tests": ["drug test", "drug screening"],
    "notice_period": ["notice period", "start date notice", "availability"],
    "salary_expectation_min": ["salary expectation", "desired salary", "expected compensation"],
    "salary_expectation_max": ["salary expectation", "desired salary", "expected compensation"],
}

HUMAN_REQUIRED_TRIGGERS = [
    "textarea",
    "salary",
    "expected compensation",
    "desired salary",
    "cover letter",
    "why do you want",
    "tell us about",
    "describe",
    "work authorization",
    "disability",
    "veteran",
    "race",
    "ethnicity",
]


def _is_human_required(label: str) -> bool:
    haystack = label.lower()
    return any(trigger in haystack for trigger in HUMAN_REQUIRED_TRIGGERS)


def _as_yes_no(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"yes", "y", "true", "1"}:
        return "yes"
    if text in {"no", "n", "false", "0"}:
        return "no"
    return None


class GenericATSAdapter:
    ats_type = "generic"

    async def autofill(
        self,
        *,
        page: Any,
        autofill: dict[str, Any],
        log: list[dict[str, Any]],
        screening_lookup: ScreeningLookup | None = None,
    ) -> dict[str, Any]:
        for key, value in autofill.items():
            if key == "work_auth":
                answer = await screening_lookup("work authorization") if screening_lookup else None
                candidate = answer or str(value or "").strip()
                if not candidate:
                    log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_skipped_manual", "field": key, "label": "work authorization"})
                    continue
                selector = (
                    "textarea[aria-label*='work authorization'], textarea[name*='work_authorization'], "
                    "input[aria-label*='work authorization'], input[name*='work_authorization']"
                )
                ok = await type_text(page, selector, candidate)
                log.append(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "event": "screening_answer_reused" if answer else "field_filled",
                        "field": key,
                        "label": "work authorization",
                        "reused": bool(answer and ok),
                    }
                )
                continue
            if not value:
                continue
            labels = SAFE_FIELD_LABELS.get(key, [])
            attempted = False
            for label in labels:
                if _is_human_required(label):
                    reused = await screening_lookup(label) if screening_lookup else None
                    if reused:
                        selector = f"textarea[aria-label*='{label}'], textarea[name*='{label.replace(' ', '_')}']"
                        ok = await type_text(page, selector, reused)
                        log.append(
                            {
                                "ts": datetime.now(UTC).isoformat(),
                                "event": "screening_answer_reused",
                                "field": key,
                                "label": label,
                                "reused": bool(ok),
                            }
                        )
                    else:
                        log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_skipped_manual", "field": key, "label": label})
                    continue
                selector = f"input[aria-label*='{label}'], input[name*='{label.replace(' ', '_')}']"
                attempted = True
                ok = await type_text(page, selector, str(value))
                if ok:
                    log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_filled", "field": key, "label": label})
                    break
                # Fuzzy dropdown fallback via shared action helper.
                select_selector = f"select[aria-label*='{label}'], select[name*='{label.replace(' ', '_')}']"
                if await wait_for(page, select_selector, timeout_ms=500):
                    if await select_option(page, select_selector, str(value)):
                        log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_selected", "field": key, "label": label})
                        break

                # Basic yes/no radio fallback for boolean-like fields.
                yn = _as_yes_no(value)
                if yn is not None:
                    radio_selector = (
                        f"input[type='radio'][value*='{yn}'], "
                        f"label:has-text('{yn}'), "
                        f"input[type='radio'][aria-label*='{label}'][value*='{yn}']"
                    )
                    if await click(page, radio_selector, timeout_ms=700):
                        log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_radio_selected", "field": key, "label": label})
                        break
                log.append(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "event": "field_fill_failed",
                        "field": key,
                        "label": label,
                    }
                )
            if not attempted and labels:
                log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_not_attempted", "field": key})

        return {"status": "completed", "submit": "manual_required"}
