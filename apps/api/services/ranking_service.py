"""Deterministic ranking engine for Today's Shortlist with explainability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.job import Job
from db.models.resume import Resume
from db.models.user_profile import UserProfile
from services.embeddings import embed_query
from services.ranking_feedback_service import get_user_job_feedback_scores
from services.vector_search import search_similar_jobs


@dataclass(slots=True)
class ScoredJob:
    job: Job
    score: float
    reasons: list[str]


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _contains_any(haystack: str, needles: list[str]) -> bool:
    base = _norm(haystack)
    return any(_norm(n) and _norm(n) in base for n in needles)


def _semantic_query(profile: UserProfile, resume_text: str | None) -> str:
    roles = ", ".join(profile.target_roles or [])
    headline = profile.headline or ""
    bio = profile.summary_bio or ""
    resume = (resume_text or "")[:600]
    return " | ".join(part for part in [roles, headline, bio, resume] if part).strip()


def rank_jobs_for_preferences(
    *,
    jobs: list[dict[str, Any]],
    target_roles: list[str],
    target_locations: list[str],
    salary_min: float | None,
    work_authorization: str | None,
    semantic_scores: dict[str, float] | None = None,
    feedback_scores: dict[str, float] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pure deterministic ranking used by API and tests."""

    ts_now = now or datetime.now(UTC)
    sem = semantic_scores or {}
    feedback = feedback_scores or {}
    output: list[dict[str, Any]] = []
    wants_sponsorship = "sponsor" in _norm(work_authorization) or "visa" in _norm(work_authorization)

    for item in jobs:
        jid = str(item.get("id"))
        title = str(item.get("title") or "")
        company = str(item.get("company") or "")
        location_city = str(item.get("location_city") or "")
        location_country = str(item.get("location_country") or "")
        posted_at = item.get("posted_at")
        posted_at_ts = item.get("posted_at_ts")
        salary_max = float(item.get("salary_max") or 0.0)
        remote = bool(item.get("remote", False))

        reasons: list[str] = []
        score = 0.0

        role_match = _contains_any(title, target_roles)
        if role_match:
            score += 0.35
            reasons.append("matches preferred role")

        if target_locations:
            loc_match = _contains_any(location_city, target_locations) or _contains_any(location_country, target_locations)
            if loc_match:
                score += 0.15
                reasons.append("matches preferred location")
            elif remote and any("remote" in _norm(loc) for loc in target_locations):
                score += 0.15
                reasons.append("matches remote preference")

        if salary_min is not None and salary_max >= float(salary_min):
            score += 0.10
            reasons.append("meets target salary")

        sponsorship_status = _norm(str(item.get("sponsorship_status") or "unknown"))
        if wants_sponsorship and sponsorship_status in {"sponsors", "unknown"}:
            score += 0.10
            reasons.append("compatible with sponsorship need")

        semantic = max(0.0, min(1.0, float(sem.get(jid, 0.0))))
        if semantic > 0.0:
            score += semantic * 0.20
            reasons.append(f"strong semantic similarity ({semantic:.2f})")

        # Adaptive preference signal from user's prior interactions.
        feedback_raw = float(feedback.get(jid, 0.0))
        feedback_adjustment = max(-0.06, min(0.06, feedback_raw * 0.02))
        if feedback_adjustment != 0.0:
            score += feedback_adjustment
            if feedback_adjustment > 0:
                reasons.append("aligned with your prior engagement")
            else:
                reasons.append("de-prioritized from prior negative signal")

        age_hours = 9999.0
        if isinstance(posted_at, datetime):
            age_hours = max((ts_now - posted_at.astimezone(UTC)).total_seconds() / 3600.0, 0.0)
        elif posted_at_ts:
            age_hours = max((ts_now.timestamp() - float(posted_at_ts)) / 3600.0, 0.0)
        recency_bonus = max(0.0, 1.0 - (age_hours / 168.0)) * 0.10
        score += recency_bonus
        if recency_bonus >= 0.03:
            reasons.append("recently posted")

        output.append(
            {
                "id": jid,
                "title": title,
                "company": company,
                "location_city": location_city,
                "location_country": location_country,
                "remote": remote,
                "salary_max": salary_max,
                "source": item.get("source"),
                "posted_at": posted_at,
                "posted_at_ts": posted_at_ts,
                "url": item.get("url"),
                "score": round(score, 6),
                "reasons": reasons[:3],
            }
        )

    output.sort(key=lambda x: (-float(x["score"]), str(x["posted_at_ts"] or 0), str(x["id"])))
    return output


async def build_todays_shortlist(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Rank tenant-scoped active jobs for a user with explanations."""

    profile = (
        await db.execute(
            select(UserProfile).where(UserProfile.tenant_id == tenant_id, UserProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return []

    latest_resume = (
        await db.execute(
            select(Resume)
            .where(Resume.tenant_id == tenant_id, Resume.user_id == user_id, Resume.is_active.is_(True))
            .order_by(Resume.updated_at.desc(), Resume.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    candidate_limit = max(1000, limit * 50)
    jobs = (
        await db.execute(
            select(Job)
            .where(Job.tenant_id == tenant_id, Job.is_active.is_(True))
            .order_by(Job.posted_at.desc().nullslast(), Job.ingested_at.desc())
            .limit(candidate_limit)
        )
    ).scalars().all()

    semantic_scores: dict[str, float] = {}
    query = _semantic_query(profile, latest_resume.original_text if latest_resume is not None else None)
    if query:
        try:
            vector = await __import__("asyncio").to_thread(embed_query, query)
            rows = await search_similar_jobs(
                query_embedding=vector,
                tenant_id=tenant_id,
                limit=200,
                db=db,
            )
            semantic_scores = {str(row.get("id")): float(row.get("similarity", 0.0)) for row in rows if row.get("id")}
        except Exception:
            semantic_scores = {}

    feedback_scores: dict[str, float] = {}
    try:
        feedback_scores = await get_user_job_feedback_scores(db, tenant_id=tenant_id, user_id=user_id)
    except Exception:
        feedback_scores = {}

    ranked = rank_jobs_for_preferences(
        jobs=[
            {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location_city": job.location_city,
                "location_country": job.location_country,
                "remote": job.remote,
                "salary_max": float(job.salary_max) if job.salary_max is not None else 0.0,
                "sponsorship_status": job.sponsorship_status,
                "posted_at": job.posted_at,
                "posted_at_ts": int(job.posted_at.timestamp()) if job.posted_at else 0,
                "source": job.source,
                "url": job.url,
            }
            for job in jobs
        ],
        target_roles=list(profile.target_roles or []),
        target_locations=list(profile.target_locations or []),
        salary_min=float(profile.target_salary_min) if profile.target_salary_min is not None else None,
        work_authorization=profile.work_authorization,
        semantic_scores=semantic_scores,
        feedback_scores=feedback_scores,
    )
    return ranked[: max(1, limit)]
