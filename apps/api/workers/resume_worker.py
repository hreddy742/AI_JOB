"""Background jobs for resume intelligence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.resume import Resume, TailoredResume
from db.models.resume_review import ResumeReview
from services.resume_parser import parse_resume_pipeline
from services.resume_reviewer_service import generate_review


async def parse_resume(ctx: dict, resume_id: str) -> dict:
    """Parse uploaded resume asynchronously."""

    db: AsyncSession = ctx["db"]
    rid = UUID(resume_id)
    resume = (await db.execute(select(Resume).where(Resume.id == rid))).scalar_one_or_none()
    if resume is None:
        return {"resume_id": resume_id, "status": "failed", "error": "resume_not_found"}
    try:
        parsed = await parse_resume_pipeline(db, rid)
        return {
            "type": "resume_parsed",
            "resume_id": resume_id,
            "status": "parsed",
            "seniority": parsed.seniority_level,
            "domain": parsed.primary_domain,
            "years": float(parsed.total_years_experience or 0),
        }
    except Exception as exc:
        resume.parse_status = "failed"
        resume.parse_error = str(exc)[:500]
        await db.commit()
        return {"type": "resume_parse_failed", "resume_id": resume_id, "status": "failed", "error": "Parsing failed"}


async def tailor_resume(ctx: dict, tailored_resume_id: str) -> dict:
    """Tailored resume job hook for external queue workers."""

    db: AsyncSession = ctx["db"]
    tr = (await db.execute(select(TailoredResume).where(TailoredResume.id == UUID(tailored_resume_id)))).scalar_one_or_none()
    if tr is None:
        return {"tailored_resume_id": tailored_resume_id, "status": "failed", "error": "not_found"}
    return {
        "type": "tailoring_complete",
        "tailored_resume_id": tailored_resume_id,
        "status": tr.status,
        "ats_score": float(tr.ats_score or 0),
        "quality_score": float(tr.quality_score or 0),
    }


async def generate_review_job(ctx: dict, review_id: str) -> dict:
    """Generate review report in the background."""

    db: AsyncSession = ctx["db"]
    review = (await db.execute(select(ResumeReview).where(ResumeReview.id == UUID(review_id)))).scalar_one_or_none()
    if review is None:
        return {"review_id": review_id, "status": "failed", "error": "review_not_found"}
    generated = await generate_review(db, review.user_id, review.tenant_id, review.resume_id, force_new=True)
    return {"type": "review_complete", "review_id": str(generated.id), "overall_score": float(generated.overall_score or 0)}


class WorkerSettings:
    """ARQ worker registration."""

    functions = [parse_resume, tailor_resume, generate_review_job]
