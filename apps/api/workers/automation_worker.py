"""Application automation worker using Playwright with safe fallbacks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.application import Application
from db.models.job import Job
from db.models.user import User
from db.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

SAFE_FIELD_LABELS: dict[str, list[str]] = {
    "first_name": ["first name", "first_name", "fname", "given name"],
    "last_name": ["last name", "last_name", "lname", "family name", "surname"],
    "email": ["email", "email address", "e-mail"],
    "phone": ["phone", "telephone", "mobile", "cell"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin profile"],
    "location": ["city", "location", "current location", "current city"],
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

ATS_STRATEGIES: dict[str, dict[str, str]] = {
    "greenhouse": {
        "resume_input": "input[type='file'][name*='resume']",
        "submit_button": "button[type='submit']",
        "field_pattern": "label -> input (match by label text)",
    },
    "lever": {
        "resume_input": ".lever-apply-form input[type='file']",
        "field_pattern": "label -> input (match by for attribute)",
    },
    "workday": {
        "notes": "SPA with dynamic rendering. Use wait_for_selector before each fill.",
        "field_pattern": "aria-label attribute matching",
    },
    "icims": {
        "notes": "Multi-page form. Track page number. Fill and advance one page at a time.",
    },
    "generic": {
        "notes": "Label text matching with fuzzy match (>0.85 similarity threshold).",
    },
}


async def get_user(user_id: str, db: AsyncSession) -> User:
    """Fetch user record by id."""

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")
    return user


async def get_user_profile(user_id: str, db: AsyncSession) -> UserProfile:
    """Fetch user profile by id."""

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == UUID(user_id)))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValueError("User profile not found")
    return profile


async def get_autofill_data(user_id: str, db: AsyncSession) -> dict[str, Any]:
    """Load profile and return autofill-safe field mapping."""

    profile = await get_user_profile(user_id, db)
    user = await get_user(user_id, db)
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": user.email,
        "phone": profile.phone,
        "linkedin_url": profile.linkedin_url,
        "location": profile.current_location,
        "work_auth": profile.work_authorization,
    }


def _label_similarity(left: str, right: str) -> float:
    """Compute label similarity for fuzzy field matching."""

    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def _is_human_required(label: str, field_type: str | None = None) -> bool:
    """Check if a field requires manual input confirmation."""

    haystack = f"{label} {field_type or ''}".lower()
    return any(trigger in haystack for trigger in HUMAN_REQUIRED_TRIGGERS)


async def _safe_fill(page: Any, selector: str, value: str) -> tuple[bool, str]:
    """Attempt to fill field with try/catch and human fallback."""

    try:
        await page.fill(selector, value)
        return True, "filled"
    except Exception as exc:
        return False, f"manual_required: {exc}"


async def automate_application(ctx: dict[str, Any], application_id: str) -> dict[str, Any]:
    """Run safe, non-submitting automation flow for one application."""

    db: AsyncSession = ctx["db"]
    app_result = await db.execute(select(Application).where(Application.id == UUID(application_id)))
    application = app_result.scalar_one_or_none()
    if application is None:
        return {"application_id": application_id, "status": "failed", "error": "Application not found"}

    job_result = await db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        return {"application_id": application_id, "status": "failed", "error": "Job not found"}

    try:
        autofill = await get_autofill_data(str(application.user_id), db)
    except ValueError as exc:
        return {"application_id": application_id, "status": "failed", "error": str(exc)}

    log: list[dict[str, Any]] = list(application.automation_log or [])
    log.append({"ts": datetime.now(UTC).isoformat(), "event": "automation_started", "job_url": job.url})

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                log.append({"ts": datetime.now(UTC).isoformat(), "event": "page_loaded"})
            except Exception as exc:
                log.append({"ts": datetime.now(UTC).isoformat(), "event": "page_load_failed", "action": "human_fallback", "error": str(exc)})
                await browser.close()
                application.automation_log = log
                await db.commit()
                return {"application_id": application_id, "status": "manual_required", "reason": "page_load_failed"}

            for key, value in autofill.items():
                if not value or key == "work_auth":
                    continue
                labels = SAFE_FIELD_LABELS.get(key, [])
                attempted = False
                for label in labels:
                    if _is_human_required(label):
                        log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_skipped_manual", "field": key, "label": label})
                        continue
                    selector = f"input[aria-label*='{label}'], input[name*='{label.replace(' ', '_')}']"
                    ok, detail = await _safe_fill(page, selector, str(value))
                    attempted = True
                    if ok:
                        log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_filled", "field": key, "label": label})
                        break
                    log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_fill_failed", "field": key, "label": label, "detail": detail})
                if not attempted:
                    log.append({"ts": datetime.now(UTC).isoformat(), "event": "field_not_attempted", "field": key})

            log.append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "event": "submit_blocked",
                    "reason": "Human must click submit",
                }
            )

            await browser.close()
    except Exception as exc:
        logger.exception("automation_worker_error")
        log.append({"ts": datetime.now(UTC).isoformat(), "event": "automation_exception", "error": str(exc)})
        application.automation_log = log
        await db.commit()
        return {"application_id": application_id, "status": "manual_required", "reason": "automation_exception"}

    application.automation_log = log
    await db.commit()
    return {"application_id": application_id, "status": "completed", "submit": "manual_required"}


class WorkerSettings:
    """ARQ worker settings for application automation."""

    functions = [automate_application]
