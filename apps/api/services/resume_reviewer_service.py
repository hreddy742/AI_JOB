"""Resume review service combining LLM + programmatic checks."""

from __future__ import annotations

import json
import logging
import re
from statistics import mean
from typing import Any
from uuid import UUID

import httpx
import language_tool_python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from textstat import flesch_reading_ease

from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls
from db.models.resume import Resume
from db.models.resume_parsed_data import ResumeParsedData
from db.models.resume_review import ResumeReview

IGNORED_RULES = {"EN_UNPAIRED_BRACKETS", "WHITESPACE_RULE"}
logger = logging.getLogger(__name__)


def _extract_bullets(text: str) -> list[str]:
    return [line.strip("- ").strip() for line in text.splitlines() if line.strip().startswith("-")]


async def _run_llm_review(resume_text: str, target_role: str, years: float, seniority: str) -> dict[str, Any]:
    prompt = f"""
You are a senior career consultant and recruiter with 20 years of experience.
Provide JSON:
{{"scores":{{"impact":0,"ats":0,"clarity":0,"completeness":0,"format":0,"overall":0}},
"verdict":"DECENT","summary_paragraph":"","top_3_issues":[],"quick_wins":[],"strengths":[],"ats_red_flags":[],"section_feedback":{{}}}}

Resume to review:
{resume_text}
Candidate's target role: {target_role}
Computed years of experience: {years}
Computed seniority: {seniority}
""".strip()
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.REVIEWER_MODEL,
                "messages": [{"role": "system", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.0},
            },
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "{}")
    return content if isinstance(content, dict) else json.loads(content)


def _fallback_llm_report(programmatic: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build deterministic fallback review when LLM endpoint is unavailable."""

    grammar_count = len(programmatic.get("grammar_errors", []))
    weak_bullet_count = int(programmatic.get("ats_checks", {}).get("weak_bullet_count", 0) or 0)
    has_email = bool(programmatic.get("ats_checks", {}).get("has_email_in_header"))
    has_phone = bool(programmatic.get("ats_checks", {}).get("has_phone_in_header"))
    readability = float(programmatic.get("readability_score") or 0.0)

    ats = max(0, min(100, 55 + (10 if has_email else -15) + (10 if has_phone else -15) - min(25, weak_bullet_count * 4)))
    clarity = max(0, min(100, 75 - min(40, grammar_count * 4) + (8 if readability >= 40 else -8)))
    impact = max(0, min(100, 60 - min(30, weak_bullet_count * 3)))
    completeness = max(0, min(100, 70 + (8 if has_email and has_phone else -8)))
    format_score = max(0, min(100, int((ats + clarity) / 2)))
    overall = int(round((impact + ats + clarity + completeness + format_score) / 5))

    issue_texts: list[str] = []
    if grammar_count:
        issue_texts.append(f"{grammar_count} grammar/style issues found.")
    if weak_bullet_count:
        issue_texts.append(f"{weak_bullet_count} weak bullets detected (e.g., 'responsible for').")
    if not has_email or not has_phone:
        issue_texts.append("Header is missing key contact details.")
    if not issue_texts:
        issue_texts.append("No critical ATS blockers detected in programmatic scan.")

    issues = [{"issue": text, "severity": "medium"} for text in issue_texts]
    quick_wins = [
        {"action": "Rewrite weak bullets with impact metrics and action verbs.", "priority": 1},
        {"action": "Ensure top section includes email and phone in ATS-friendly plain text.", "priority": 2},
        {"action": "Reduce grammar/style issues and keep bullet formatting consistent.", "priority": 3},
    ]

    return {
        "scores": {
            "impact": impact,
            "ats": ats,
            "clarity": clarity,
            "completeness": completeness,
            "format": format_score,
            "overall": overall,
        },
        "verdict": "DECENT" if overall >= 65 else "NEEDS_WORK",
        "summary_paragraph": "LLM reviewer unavailable; generated deterministic review from programmatic analysis.",
        "top_3_issues": issues[:3],
        "quick_wins": quick_wins,
        "strengths": ["Programmatic quality scan completed successfully."],
        "ats_red_flags": issue_texts[:2],
        "section_feedback": {"fallback_reason": reason},
    }


def _normalize_list_of_dicts(value: Any, text_key: str) -> list[dict[str, Any]]:
    """Normalize list fields to `list[dict]` for schema-compatible persistence."""

    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(item)
        elif isinstance(item, str):
            normalized.append({text_key: item})
    return normalized


def _programmatic_scan(resume_text: str) -> dict[str, Any]:
    grammar_errors: list[dict[str, Any]] = []
    try:
        tool = language_tool_python.LanguageTool("en-US")
        matches = tool.check(resume_text)
        grammar_errors = [
            {"message": m.message, "suggestions": m.replacements[:3], "offset": m.offset}
            for m in matches
            if m.ruleId not in IGNORED_RULES
        ]
    except Exception as exc:
        logger.warning("resume_review_grammar_scan_unavailable", extra={"error": str(exc)})
    header = resume_text[:300]
    has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+", header))
    has_phone = bool(re.search(r"\d{3}[\-\.\s]\d{3}[\-\.\s]\d{4}", header))
    weak_bullet_count = len(re.findall(r"(responsible for|duties included|tasks included|helped with)", resume_text, re.I))
    bullets = _extract_bullets(resume_text)
    avg_bullet_length = mean([len(b) for b in bullets]) if bullets else 0
    readability = flesch_reading_ease(resume_text)
    return {
        "grammar_errors": grammar_errors,
        "ats_checks": {
            "has_email_in_header": has_email,
            "has_phone_in_header": has_phone,
            "weak_bullet_count": weak_bullet_count,
            "avg_bullet_length": avg_bullet_length,
        },
        "readability_score": readability,
    }


async def generate_review(
    db: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    resume_id: UUID,
    review_type: str = "expert",
    force_new: bool = False,
) -> ResumeReview:
    """Get cached review or generate a fresh one."""

    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    if not force_new:
        cached = (
            await db.execute(
                select(ResumeReview)
                .where(ResumeReview.resume_id == resume_id, ResumeReview.user_id == user_id, ResumeReview.review_type == review_type)
                .order_by(ResumeReview.created_at.desc())
            )
        ).scalar_one_or_none()
        if cached is not None:
            return cached

    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    parsed = (
        await db.execute(select(ResumeParsedData).where(ResumeParsedData.resume_id == resume_id, ResumeParsedData.user_id == user_id))
    ).scalar_one_or_none()
    years = float(parsed.total_years_experience or 0) if parsed else 0.0
    seniority = parsed.seniority_level if parsed else "entry"

    programmatic = _programmatic_scan(resume.original_text)
    llm_report: dict[str, Any]
    try:
        llm_report = await _run_llm_review(resume.original_text, "", years, seniority or "entry")
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("resume_review_llm_unavailable", extra={"resume_id": str(resume_id), "error": str(exc)})
        llm_report = _fallback_llm_report(programmatic, reason=str(exc))
    full_report = {"llm": llm_report, "programmatic": programmatic}
    scores = llm_report.get("scores", {})
    key_issues = _normalize_list_of_dicts(llm_report.get("top_3_issues", []), "issue")
    quick_wins = _normalize_list_of_dicts(llm_report.get("quick_wins", []), "action")

    review = ResumeReview(
        user_id=user_id,
        tenant_id=tenant_id,
        resume_id=resume_id,
        review_type=review_type,
        overall_score=scores.get("overall"),
        ats_score=scores.get("ats"),
        impact_score=scores.get("impact"),
        clarity_score=scores.get("clarity"),
        completeness_score=scores.get("completeness"),
        format_score=scores.get("format"),
        full_report=full_report,
        summary_text=llm_report.get("summary_paragraph"),
        key_issues=key_issues,
        quick_wins=quick_wins,
        model_used=settings.REVIEWER_MODEL,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review
