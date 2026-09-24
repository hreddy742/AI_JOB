"""Screening answer memory service with strict tenant/user isolation."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.llm_telemetry import ollama_chat
from db.models.job import Job
from db.models.resume import Resume
from db.models.resume_parsed_data import ResumeParsedData
from db.models.user_profile import UserProfile
from db.models.screening_answer import ScreeningAnswer


def normalize_screening_question(question: str) -> str:
    """Normalize question text deterministically for hashing."""

    text = (question or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ?!:/\-\(\)\.,]", "", text)
    return text.strip()


def screening_question_hash(question: str) -> str:
    """Stable SHA-256 hash of normalized question text."""

    normalized = normalize_screening_question(question)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _question_similarity(left: str, right: str) -> float:
    left_normalized = normalize_screening_question(left)
    right_normalized = normalize_screening_question(right)
    if not left_normalized or not right_normalized:
        return 0.0
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    containment = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    sequence_score = SequenceMatcher(a=left_normalized, b=right_normalized).ratio()
    return max(overlap, containment, sequence_score)


async def get_reusable_screening_answer(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    question: str,
    ats_type: str = "generic",
    job_category: str = "general",
    min_confidence: float = 0.7,
) -> ScreeningAnswer | None:
    """Fetch best reusable answer for a user/tenant/question hash and ATS type."""

    q_hash = screening_question_hash(question)
    rows = (
        await db.execute(
            select(ScreeningAnswer)
            .where(
                ScreeningAnswer.tenant_id == tenant_id,
                ScreeningAnswer.user_id == user_id,
                ScreeningAnswer.question_hash == q_hash,
                ScreeningAnswer.ats_type.in_([ats_type, "generic"]),
                ScreeningAnswer.job_category.in_([job_category, "general"]),
                ScreeningAnswer.confidence >= min_confidence,
            )
            .order_by(desc(ScreeningAnswer.confidence), desc(ScreeningAnswer.success_count), desc(ScreeningAnswer.use_count))
            .limit(1)
        )
    ).scalars().all()
    if not rows:
        fallback_rows = (
            await db.execute(
                select(ScreeningAnswer)
                .where(
                    ScreeningAnswer.tenant_id == tenant_id,
                    ScreeningAnswer.user_id == user_id,
                    ScreeningAnswer.ats_type.in_([ats_type, "generic"]),
                    ScreeningAnswer.job_category.in_([job_category, "general"]),
                    ScreeningAnswer.confidence >= max(0.55, min_confidence - 0.15),
                )
                .order_by(desc(ScreeningAnswer.updated_at))
                .limit(25)
            )
        ).scalars().all()
        scored = [
            (item, _question_similarity(question, item.question_text))
            for item in fallback_rows
        ]
        scored = [item for item in scored if item[1] >= 0.82]
        if not scored:
            return None
        scored.sort(
            key=lambda item: (
                -item[1],
                -float(item[0].confidence or 0.0),
                -int(item[0].success_count or 0),
                -int(item[0].use_count or 0),
            )
        )
        best = scored[0][0]
    else:
        best = rows[0]
    best.use_count = int(best.use_count or 0) + 1
    best.last_used_at = datetime.now(UTC)
    return best


async def upsert_screening_answer(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    question: str,
    answer: str,
    ats_type: str = "generic",
    job_category: str = "general",
    confidence: float = 0.75,
    mark_success: bool = False,
    answer_source: str = "user",
) -> ScreeningAnswer:
    """Create/update a screening answer memory row for later deterministic reuse."""

    q_hash = screening_question_hash(question)
    existing = (
        await db.execute(
            select(ScreeningAnswer).where(
                ScreeningAnswer.tenant_id == tenant_id,
                ScreeningAnswer.user_id == user_id,
                ScreeningAnswer.question_hash == q_hash,
                ScreeningAnswer.ats_type == ats_type,
                ScreeningAnswer.job_category == job_category,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = ScreeningAnswer(
            tenant_id=tenant_id,
            user_id=user_id,
            ats_type=ats_type,
            job_category=job_category,
            question_hash=q_hash,
            question_text=normalize_screening_question(question),
            answer_text=answer,
            confidence=max(0.0, min(1.0, confidence)),
            answer_source=answer_source,
            use_count=1 if mark_success else 0,
            success_count=1 if mark_success else 0,
            last_used_at=datetime.now(UTC) if mark_success else None,
        )
        db.add(existing)
        return existing

    existing.answer_text = answer
    existing.question_text = normalize_screening_question(question)
    existing.confidence = max(float(existing.confidence or 0.0), max(0.0, min(1.0, confidence)))
    existing.answer_source = answer_source
    if mark_success:
        existing.use_count = int(existing.use_count or 0) + 1
        existing.success_count = int(existing.success_count or 0) + 1
        existing.last_used_at = datetime.now(UTC)
    return existing


def _format_decimal(value: Decimal | float | int | None) -> str:
    if value is None:
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


async def _load_drafting_context(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    job_id: UUID,
) -> dict[str, Any]:
    profile = (
        await db.execute(
            select(UserProfile).where(UserProfile.tenant_id == tenant_id, UserProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    job = (
        await db.execute(select(Job).where(Job.tenant_id == tenant_id, Job.id == job_id))
    ).scalar_one_or_none()
    resume = (
        await db.execute(
            select(Resume)
            .where(Resume.tenant_id == tenant_id, Resume.user_id == user_id)
            .order_by(Resume.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    parsed = None
    if resume is not None:
        parsed = (
            await db.execute(
                select(ResumeParsedData).where(
                    ResumeParsedData.tenant_id == tenant_id,
                    ResumeParsedData.user_id == user_id,
                    ResumeParsedData.resume_id == resume.id,
                )
            )
        ).scalar_one_or_none()

    work_titles: list[str] = []
    if parsed is not None:
        for item in (parsed.work_experience or [])[:3]:
            title = str(item.get("title") or "").strip()
            company = str(item.get("company") or "").strip()
            if title and company:
                work_titles.append(f"{title} at {company}")
            elif title:
                work_titles.append(title)

    return {
        "job": job,
        "profile": profile,
        "resume_summary": (parsed.summary_text if parsed is not None else "") or "",
        "skills": (parsed.skills_technical if parsed is not None else []) or [],
        "recent_titles": work_titles,
    }


def _deterministic_fallback_answer(question: str, context: dict[str, Any]) -> tuple[str, float]:
    q = normalize_screening_question(question)
    profile = context.get("profile")
    if "work authorization" in q or "sponsor" in q or "visa" in q:
        auth = str(
            getattr(profile, "us_work_authorization", None)
            or getattr(profile, "work_authorization", "")
            or ""
        ).strip()
        if auth:
            return f"I currently have {auth} work authorization status.", 0.8
        return "I can clarify my work authorization details during the application review.", 0.45
    if "salary" in q or "compensation" in q or "pay" in q:
        low = _format_decimal(
            (getattr(profile, "salary_expectation_min", None) or getattr(profile, "target_salary_min", None))
            if profile is not None
            else None
        )
        high = _format_decimal(
            (getattr(profile, "salary_expectation_max", None) or getattr(profile, "target_salary_max", None))
            if profile is not None
            else None
        )
        if low and high:
            return f"My target compensation range is ${low}-${high} annually, depending on scope and total package.", 0.7
        if low:
            return f"My target compensation starts around ${low} annually, depending on scope and total package.", 0.65
    if "why" in q and ("company" in q or "role" in q):
        job = context.get("job")
        title = str(getattr(job, "title", "this role") or "this role")
        company = str(getattr(job, "company", "your team") or "your team")
        return f"I am interested in {title} at {company} because it aligns with my relevant experience and impact-oriented work style.", 0.6
    return "My background aligns with the role requirements, and I can provide a concise role-specific response after review.", 0.4


async def _llm_draft_answer(question: str, context: dict[str, Any]) -> tuple[str, float]:
    profile = context.get("profile")
    job = context.get("job")
    if job is None:
        return _deterministic_fallback_answer(question, context)

    system_prompt = (
        "You write short, factual screening-question drafts. "
        "Use only provided profile/resume/job facts. "
        "Never invent employers, years, visas, education, or numbers. "
        "If missing facts, write a cautious response without fabricated claims. "
        "Return strict JSON with keys: answer, confidence."
    )
    user_payload = {
        "question": question,
        "profile": {
            "work_authorization": str(
                getattr(profile, "us_work_authorization", None) or getattr(profile, "work_authorization", "") or ""
            )
            if profile is not None
            else "",
            "requires_us_sponsorship": getattr(profile, "requires_us_sponsorship", None) if profile is not None else None,
            "legally_allowed_to_work_in_us": getattr(profile, "legally_allowed_to_work_in_us", None)
            if profile is not None
            else None,
            "target_salary_min": _format_decimal(
                (getattr(profile, "salary_expectation_min", None) or getattr(profile, "target_salary_min", None))
                if profile is not None
                else None
            ),
            "target_salary_max": _format_decimal(
                (getattr(profile, "salary_expectation_max", None) or getattr(profile, "target_salary_max", None))
                if profile is not None
                else None
            ),
            "years_experience": getattr(profile, "years_experience", None) if profile is not None else None,
            "current_location": str(getattr(profile, "current_location", "") or "") if profile is not None else "",
        },
        "job": {
            "title": str(getattr(job, "title", "") or ""),
            "company": str(getattr(job, "company", "") or ""),
            "description_excerpt": str(getattr(job, "description", "") or "")[:1000],
        },
        "resume_summary": context.get("resume_summary") or "",
        "skills": list(context.get("skills") or [])[:20],
        "recent_titles": list(context.get("recent_titles") or [])[:5],
    }

    try:
        data = await ollama_chat(
            flow="screening_answer_draft",
            model=settings.COPILOT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(user_payload)},
            ],
            output_format="json",
            options={"temperature": 0.15},
            stream=False,
            timeout_s=45.0,
        )
        raw = data.get("message", {}).get("content", "{}")
        parsed = {}
        try:
            import json as _json

            parsed = _json.loads(raw)
        except Exception:
            parsed = {}
        answer = str(parsed.get("answer") or "").strip()
        try:
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.55))))
        except (TypeError, ValueError):
            confidence = 0.55
        if answer:
            return answer, confidence
    except Exception:
        pass

    return _deterministic_fallback_answer(question, context)


async def draft_screening_answer(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    job_id: UUID,
    question: str,
    ats_type: str = "generic",
    job_category: str = "general",
) -> dict[str, Any]:
    """Generate a reviewed draft for unknown screening questions with safe grounding."""

    reusable = await get_reusable_screening_answer(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        question=question,
        ats_type=ats_type,
        job_category=job_category,
        min_confidence=0.7,
    )
    if reusable is not None:
        return {
            "source": "memory",
            "answer": reusable.answer_text,
            "confidence": float(reusable.confidence or 0.7),
            "review_required": False,
            "question_hash": reusable.question_hash,
        }

    context = await _load_drafting_context(db, tenant_id=tenant_id, user_id=user_id, job_id=job_id)
    if job_category == "general":
        job = context.get("job")
        job_category = str(getattr(job, "category", "general") or "general").strip().lower() or "general"
    answer, confidence = await _llm_draft_answer(question, context)
    return {
        "source": "draft",
        "answer": answer,
        "confidence": confidence,
        "review_required": True,
        "question_hash": screening_question_hash(question),
    }
