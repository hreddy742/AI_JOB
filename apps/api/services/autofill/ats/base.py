"""ATS autofill adapter interface."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

ScreeningLookup = Callable[[str], Awaitable[str | None]]


class ATSAutofillAdapter(Protocol):
    """Adapter contract for ATS-specific autofill behavior."""

    ats_type: str

    async def autofill(
        self,
        *,
        page: Any,
        autofill: dict[str, Any],
        log: list[dict[str, Any]],
        screening_lookup: ScreeningLookup | None = None,
    ) -> dict[str, Any]:
        ...
