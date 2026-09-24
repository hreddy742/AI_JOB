"""Shared helpers for ATS autofill adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.autofill.actions import select_option, type_text, wait_for
from services.autofill.ats.base import ScreeningLookup
from services.autofill.ats.generic import SAFE_FIELD_LABELS


async def fill_visible_fields(
    *,
    target: Any,
    autofill: dict[str, Any],
    log: list[dict[str, Any]],
    screening_lookup: ScreeningLookup | None = None,
    adapter_name: str,
) -> bool:
    """Fill obvious visible fields while skipping hidden honeypots."""

    filled_any = False
    hidden_guard = ":not([type='hidden']):not([aria-hidden='true']):not([hidden]):not([style*='display:none'])"
    for key, value in autofill.items():
        if not value:
            continue
        if key == "work_auth" and screening_lookup:
            answer = await screening_lookup("work authorization")
            if answer:
                selector = (
                    "textarea[aria-label*='work authorization'], textarea[name*='work_authorization'], "
                    "input[aria-label*='work authorization'], input[name*='work_authorization']"
                )
                if await type_text(target, selector, answer):
                    filled_any = True
                    log.append(
                        {
                            "ts": datetime.now(UTC).isoformat(),
                            "event": "screening_answer_reused",
                            "field": key,
                            "adapter": adapter_name,
                        }
                    )
                    continue
        for label in SAFE_FIELD_LABELS.get(key, []):
            input_selector = (
                f"input{hidden_guard}[aria-label*='{label}'], "
                f"input{hidden_guard}[name*='{label.replace(' ', '_')}']"
            )
            if await wait_for(target, input_selector, timeout_ms=700):
                if await type_text(target, input_selector, str(value)):
                    filled_any = True
                    log.append(
                        {
                            "ts": datetime.now(UTC).isoformat(),
                            "event": "field_filled",
                            "field": key,
                            "label": label,
                            "adapter": adapter_name,
                        }
                    )
                    break
            select_selector = (
                f"select{hidden_guard}[aria-label*='{label}'], "
                f"select{hidden_guard}[name*='{label.replace(' ', '_')}']"
            )
            if await wait_for(target, select_selector, timeout_ms=500):
                if await select_option(target, select_selector, str(value)):
                    filled_any = True
                    log.append(
                        {
                            "ts": datetime.now(UTC).isoformat(),
                            "event": "field_selected",
                            "field": key,
                            "label": label,
                            "adapter": adapter_name,
                        }
                    )
                    break
    return filled_any
