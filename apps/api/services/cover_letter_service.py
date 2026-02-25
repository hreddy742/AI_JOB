"""Cover letter generation service."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls
from db.models.cover_letter import CoverLetter
from db.models.job import Job
from db.models.resume import Resume, TailoredResume
from db.models.resume_parsed_data import ResumeParsedData

BANNED_PHRASES = [
    "i am writing to express",
    "i am excited to apply",
    "i believe i would be a great fit",
    "passionate about",
    "team player",
    "hard worker",
    "detail-oriented",
    "fast learner",
    "results-driven",
    "dynamic",
]


async def _generate_letter(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.WRITER_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.4},
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = payload.get("message", {}).get("content", "")
    return content.strip()


def _validate_letter(candidate: str, raw_resume: str) -> tuple[str, list[str]]:
    words = candidate.split()
    if len(words) > 400:
        candidate = " ".join(words[:300])
    flags = [phrase for phrase in BANNED_PHRASES if phrase in candidate.lower()]
    numeric_tokens = set(re.findall(r"\d+(?:\.\d+)?%?", candidate))
    original_numeric = set(re.findall(r"\d+(?:\.\d+)?%?", raw_resume))
    if not numeric_tokens.issubset(original_numeric):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generated letter failed integrity checks")
    return candidate, flags


async def create_cover_letter(
    db: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    source_resume_id: UUID,
    job_id: UUID | None,
    tone: str = "professional",
    hiring_manager_name: str | None = None,
) -> CoverLetter:
    """Generate and store a role-specific cover letter."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    resume = (
        await db.execute(select(Resume).where(Resume.id == source_resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    parsed = (
        await db.execute(select(ResumeParsedData).where(ResumeParsedData.resume_id == source_resume_id, ResumeParsedData.user_id == user_id))
    ).scalar_one_or_none()

    job = None
    if job_id is not None:
        job = (await db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))).scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    best_achievement = ""
    if parsed and parsed.work_experience:
        first = parsed.work_experience[0]
        best_achievement = (first.get("bullets") or [""])[0]
    prompt = f"""
You are a professional cover letter writer with 20 years of experience.
Write a strong, specific cover letter with zero fabricated claims.
Output only the letter starting with: Subject: ...

Candidate Information:
Name: {parsed.contact_name if parsed else ""}
Most Recent Title: {(parsed.work_experience[0].get("title") if parsed and parsed.work_experience else "")}
Most Recent Company: {(parsed.work_experience[0].get("company") if parsed and parsed.work_experience else "")}
Years of Experience: {parsed.total_years_experience if parsed else 0}
Most Relevant Skills: {", ".join((parsed.skills_technical if parsed else [])[:10])}
Strongest Achievement: {best_achievement}
Target Company: {job.company if job else ""}
Target Role: {job.title if job else ""}
Hiring Manager: {hiring_manager_name or "Hiring Manager"}
Tone: {tone}
Job Description: {job.description if job else ""}
Resume Source Text: {resume.original_text[:12000]}
""".strip()

    content = await _generate_letter(prompt)
    content, flags = _validate_letter(content, resume.original_text)

    record = CoverLetter(
        user_id=user_id,
        tenant_id=tenant_id,
        source_resume_id=source_resume_id,
        job_id=job_id,
        job_title_target=job.title if job else None,
        company_target=job.company if job else None,
        hiring_manager_name=hiring_manager_name,
        tone=tone,
        content=content,
        word_count=len(content.split()),
        generation_model=settings.WRITER_MODEL,
        status="draft" if flags else "final",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_cover_letter(db: AsyncSession, user_id: UUID, tenant_id: UUID, cover_letter_id: UUID) -> CoverLetter:
    """Fetch one cover letter by ID."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    item = (
        await db.execute(select(CoverLetter).where(CoverLetter.id == cover_letter_id, CoverLetter.user_id == user_id))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter not found")
    return item
