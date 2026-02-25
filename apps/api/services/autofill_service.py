"""Application autofill profile service."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import apply_tenant_rls, apply_user_rls
from db.models.resume import Resume
from db.models.resume_parsed_data import ResumeParsedData
from db.models.user import User
from db.models.user_profile import UserProfile


def _extract_year(value: str | None) -> str:
    if not value:
        return ""
    m = re.search(r"(19|20)\d{2}", value)
    return m.group(0) if m else ""


def _extract_city_state(location: str | None) -> tuple[str, str]:
    if not location:
        return "", ""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return (parts[0], "") if parts else ("", "")


async def build_autofill_profile(db: AsyncSession, user_id: UUID, tenant_id: UUID, resume_id: UUID) -> dict[str, Any]:
    """Build standardized autofill payload from parsed resume + user profile."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    parsed = (
        await db.execute(select(ResumeParsedData).where(ResumeParsedData.resume_id == resume_id, ResumeParsedData.user_id == user_id))
    ).scalar_one_or_none()
    if parsed is None:
        parse_status = (resume.parse_status or "").lower()
        if parse_status in {"pending", "processing"}:
            return {
                "status": "processing",
                "parse_status": parse_status,
                "detail": "Resume parsing is still in progress. Retry shortly.",
            }
        if parse_status == "failed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resume parsing failed. Re-upload resume and try again.",
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parsed resume data not found")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    most_recent = parsed.work_experience[0] if parsed.work_experience else {}
    city, state = _extract_city_state(parsed.contact_location)
    name_parts = (parsed.contact_name or "").split()
    top_edu = parsed.education[0] if parsed.education else {}
    return {
        "first_name": name_parts[0] if name_parts else "",
        "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        "full_name": parsed.contact_name or "",
        "email": parsed.contact_email or user.email,
        "phone": parsed.contact_phone or "",
        "city": city,
        "state": state,
        "linkedin_url": parsed.contact_linkedin or "",
        "github_url": parsed.contact_github or "",
        "portfolio_url": parsed.contact_website or "",
        "current_title": most_recent.get("title", ""),
        "current_company": most_recent.get("company", ""),
        "years_experience": str(int(float(parsed.total_years_experience or 0))),
        "work_authorization": (profile.work_authorization if profile else "") or "",
        "requires_sponsorship": bool(getattr(profile, "requires_sponsorship", False)) if profile else False,
        "skills_summary": ", ".join((parsed.skills_technical or [])[:20]),
        "highest_degree": top_edu.get("degree", ""),
        "school_name": top_edu.get("institution", ""),
        "graduation_year": _extract_year(top_edu.get("end_date")),
        "resume_file_path": resume.file_path,
    }
