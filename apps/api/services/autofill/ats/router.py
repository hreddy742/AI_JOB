"""ATS adapter resolver."""

from __future__ import annotations

from services.autofill.ats.base import ATSAutofillAdapter
from services.autofill.ats.ashby import AshbyATSAdapter
from services.autofill.ats.bamboohr import BambooHRATSAdapter
from services.autofill.ats.generic import GenericATSAdapter
from services.autofill.ats.greenhouse import GreenhouseATSAdapter
from services.autofill.ats.lever import LeverATSAdapter
from services.autofill.ats.workday import WorkdayATSAdapter

_ADAPTERS: dict[str, ATSAutofillAdapter] = {
    "ashby": AshbyATSAdapter(),
    "bamboohr": BambooHRATSAdapter(),
    "generic": GenericATSAdapter(),
    "greenhouse": GreenhouseATSAdapter(),
    "lever": LeverATSAdapter(),
    "workday": WorkdayATSAdapter(),
}


def get_ats_adapter(ats_type: str | None) -> ATSAutofillAdapter:
    return _ADAPTERS.get((ats_type or "generic").lower(), _ADAPTERS["generic"])
