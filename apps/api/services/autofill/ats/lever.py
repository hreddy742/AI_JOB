"""Lever ATS autofill adapter."""

from __future__ import annotations

from services.autofill.ats.base import ScreeningLookup
from services.autofill.ats.common import fill_visible_fields


class LeverATSAdapter:
    ats_type = "lever"

    async def autofill(self, *, page, autofill, log, screening_lookup: ScreeningLookup | None = None) -> dict[str, str]:
        filled_any = await fill_visible_fields(
            target=page,
            autofill=autofill,
            log=log,
            screening_lookup=screening_lookup,
            adapter_name=self.ats_type,
        )
        if not filled_any:
            return {"status": "manual_required", "reason": "lever_no_fillable_fields"}
        return {"status": "waiting_user_submit", "submit": "manual_required"}
