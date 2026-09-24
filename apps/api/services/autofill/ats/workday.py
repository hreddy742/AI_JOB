"""Workday ATS autofill adapter with iframe-aware field traversal."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.autofill.actions import click, scroll, select_option, type_text, upload_file, wait_for
from services.autofill.ats.base import ScreeningLookup
from services.autofill.ats.generic import SAFE_FIELD_LABELS


class WorkdayATSAdapter:
    ats_type = "workday"

    async def _candidate_frames(self, page: Any) -> list[Any]:
        frames = [frame for frame in page.frames if frame.url]
        workday_frames = [frame for frame in frames if "workday" in frame.url.lower() or "myworkdayjobs" in frame.url.lower()]
        return workday_frames or frames

    async def autofill(
        self,
        *,
        page: Any,
        autofill: dict[str, Any],
        log: list[dict[str, Any]],
        screening_lookup: ScreeningLookup | None = None,
    ) -> dict[str, Any]:
        frames = await self._candidate_frames(page)
        if not frames:
            return {"status": "manual_required", "reason": "workday_frame_not_found"}

        filled_any = False
        for frame in frames:
            for key, value in autofill.items():
                if not value and key != "work_auth":
                    continue
                for label in SAFE_FIELD_LABELS.get(key, []):
                    input_selector = f"input[aria-label*='{label}'], input[name*='{label.replace(' ', '_')}']"
                    if await wait_for(frame, input_selector, timeout_ms=1200):
                        await scroll(frame, input_selector)
                        ok = await type_text(frame, input_selector, str(value))
                        if ok:
                            filled_any = True
                            log.append(
                                {
                                    "ts": datetime.now(UTC).isoformat(),
                                    "event": "field_filled",
                                    "field": key,
                                    "label": label,
                                    "adapter": "workday",
                                }
                            )
                            break
                    select_selector = f"select[aria-label*='{label}'], select[name*='{label.replace(' ', '_')}']"
                    if await wait_for(frame, select_selector, timeout_ms=600):
                        ok = await select_option(frame, select_selector, str(value))
                        if ok:
                            filled_any = True
                            log.append(
                                {
                                    "ts": datetime.now(UTC).isoformat(),
                                    "event": "field_selected",
                                    "field": key,
                                    "label": label,
                                    "adapter": "workday",
                                }
                            )
                            break

                if key == "work_auth" and value:
                    lowered = str(value).lower()
                    radio_value = "yes" if any(tok in lowered for tok in ["citizen", "authorized", "no sponsorship"]) else "no"
                    radio_selector = (
                        f"input[type='radio'][value*='{radio_value}'], "
                        f"label:has-text('{radio_value}')"
                    )
                    if await click(frame, radio_selector, timeout_ms=800):
                        filled_any = True
                        log.append(
                            {
                                "ts": datetime.now(UTC).isoformat(),
                                "event": "field_radio_selected",
                                "field": "work_auth",
                                "adapter": "workday",
                            }
                        )

                if key == "work_auth" and screening_lookup:
                    answer = await screening_lookup("work authorization")
                    if answer:
                        ta_selector = "textarea[aria-label*='work authorization'], textarea[name*='work_authorization']"
                        if await wait_for(frame, ta_selector, timeout_ms=900):
                            if await type_text(frame, ta_selector, answer):
                                filled_any = True
                                log.append(
                                    {
                                        "ts": datetime.now(UTC).isoformat(),
                                        "event": "screening_answer_reused",
                                        "field": "work_auth",
                                        "adapter": "workday",
                                    }
                                )

                if key == "resume_file_path" and value:
                    file_selector = "input[type='file']"
                    if await wait_for(frame, file_selector, timeout_ms=600):
                        if await upload_file(frame, file_selector, str(value)):
                            filled_any = True
                            log.append(
                                {
                                    "ts": datetime.now(UTC).isoformat(),
                                    "event": "file_uploaded",
                                    "field": "resume_file_path",
                                    "adapter": "workday",
                                }
                            )

            for next_selector in ("button:has-text('Next')", "button:has-text('Continue')"):
                await click(frame, next_selector, timeout_ms=1000)

        if not filled_any:
            return {"status": "manual_required", "reason": "workday_no_fillable_fields"}
        return {"status": "completed", "submit": "manual_required"}
