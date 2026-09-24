"""Structured hard filters for job-user matching."""

from __future__ import annotations


def passes_structured_filters(user_prefs: dict, job: dict) -> bool:
    """Return False when a job should be hard-rejected for a user."""

    if user_prefs.get("needs_sponsorship"):
        if job.get("sponsorship_status") == "no_sponsor":
            return False

    if user_prefs.get("location_type") == "remote":
        if not bool(job.get("is_remote")):
            return False

    if user_prefs.get("min_salary") and job.get("salary_max"):
        if float(job["salary_max"]) < float(user_prefs["min_salary"]):
            return False

    excluded = user_prefs.get("excluded_companies") or []
    if excluded:
        company = str(job.get("company", "")).lower()
        if any(str(item).lower() in company for item in excluded):
            return False

    return True
