"""Browser-agent preflight intelligence helpers for Phase 7."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlparse
from uuid import UUID

from core.config import settings
from core.redis import get_redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.employer_account import EmployerAccount
from db.models.job import Job
from db.models.job_requirement import JobRequirement
from db.models.resume import Resume, TailoredResume

_TRANSIENT_SECRET_FIELDS = {
    "account_password",
    "signup_password",
    "verification_code",
    "otp_code",
}


def employer_domain_from_url(url: str) -> str:
    """Return a stable employer domain from a job URL."""

    hostname = (urlparse(url or "").hostname or "").strip().lower()
    return hostname[4:] if hostname.startswith("www.") else hostname


async def get_job_intelligence_snapshot(db: AsyncSession, *, job: Job) -> dict:
    """Return structured job intelligence, computing a fallback snapshot when needed."""

    row = (
        await db.execute(
            select(JobRequirement).where(JobRequirement.tenant_id == job.tenant_id, JobRequirement.job_id == job.id)
        )
    ).scalar_one_or_none()
    if row is not None:
        return {
            "role_title": job.title,
            "job_type": str(job.job_type.value if hasattr(job.job_type, "value") else job.job_type),
            "location": {
                "city": job.location_city,
                "state": job.location_state,
                "country": job.location_country,
            },
            "experience_level": row.seniority,
            "required_skills": row.must_have_skills or [],
            "preferred_skills": row.nice_to_have_skills or [],
            "salary": {
                "min": row.salary_extracted_min,
                "max": row.salary_extracted_max,
                "period": row.salary_period,
                "raw": row.salary_text_raw,
            },
            "sponsorship": row.visa_sponsorship,
            "citizenship_restrictions": {
                "us_citizens_only": bool(row.us_citizens_only),
                "security_clearance_required": bool(row.security_clearance_required),
            },
            "remote_mode": getattr(job, "work_mode", "unknown") or "unknown",
            "domain": getattr(job, "category", "Other") or "Other",
            "role_family": getattr(row, "role_family", "other") or "other",
            "confidence": float(row.confidence or 0.0),
        }

    from services.job_requirements_service import analyze_job_requirements

    fallback = analyze_job_requirements(job.title or "", job.description or "")
    return {
        "role_title": job.title,
        "job_type": str(job.job_type.value if hasattr(job.job_type, "value") else job.job_type),
        "location": {
            "city": job.location_city,
            "state": job.location_state,
            "country": job.location_country,
        },
        "experience_level": fallback.get("seniority"),
        "required_skills": fallback.get("must_have_skills") or [],
        "preferred_skills": fallback.get("nice_to_have_skills") or [],
        "salary": {
            "min": fallback.get("salary_extracted_min"),
            "max": fallback.get("salary_extracted_max"),
            "period": fallback.get("salary_period"),
            "raw": fallback.get("salary_text_raw"),
        },
        "sponsorship": fallback.get("visa_sponsorship"),
        "citizenship_restrictions": {
            "us_citizens_only": bool(fallback.get("us_citizens_only")),
            "security_clearance_required": bool(fallback.get("security_clearance_required")),
        },
        "remote_mode": fallback.get("work_mode"),
        "domain": getattr(job, "category", "Other") or "Other",
        "role_family": fallback.get("role_family"),
        "confidence": float(fallback.get("confidence") or 0.0),
    }


async def find_best_tailored_resume(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    job_id: UUID,
    source_resume_id: UUID | None,
) -> TailoredResume | None:
    """Return the best approved tailored resume for this job/resume pair."""

    if source_resume_id is None:
        return None
    return (
        await db.execute(
            select(TailoredResume)
            .where(
                TailoredResume.tenant_id == tenant_id,
                TailoredResume.user_id == user_id,
                TailoredResume.job_id == job_id,
                TailoredResume.source_resume_id == source_resume_id,
                TailoredResume.status == "approved",
            )
            .order_by(TailoredResume.updated_at.desc(), TailoredResume.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def materialize_tailored_resume_upload(tailored_resume: TailoredResume) -> str:
    """Render a tailored resume to a deterministic local upload path for browser use."""

    temp_root = Path(gettempdir()) / "apex-browser-agent-v1" / "tailored"
    temp_root.mkdir(parents=True, exist_ok=True)
    target = temp_root / f"{tailored_resume.id}.txt"
    current = (tailored_resume.tailored_text or "").strip()
    if (not target.exists()) or target.read_text(encoding="utf-8", errors="ignore") != current:
        target.write_text(current, encoding="utf-8")
    return str(target)


async def get_resume_file_path(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    resume_id: UUID | None,
) -> str | None:
    """Return the persisted base resume file path for upload fallback."""

    if resume_id is None:
        resume = (
            await db.execute(
                select(Resume)
                .where(Resume.tenant_id == tenant_id, Resume.user_id == user_id, Resume.is_active.is_(True))
                .order_by(Resume.is_primary.desc(), Resume.updated_at.desc(), Resume.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return getattr(resume, "file_path", None)
    resume = (
        await db.execute(
            select(Resume).where(Resume.tenant_id == tenant_id, Resume.user_id == user_id, Resume.id == resume_id)
        )
    ).scalar_one_or_none()
    return getattr(resume, "file_path", None)


async def get_employer_account(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    provider: str,
    employer_domain: str,
) -> EmployerAccount | None:
    """Return known employer account memory for a provider/domain pair."""

    if not employer_domain:
        return None
    return (
        await db.execute(
            select(EmployerAccount).where(
                EmployerAccount.tenant_id == tenant_id,
                EmployerAccount.user_id == user_id,
                EmployerAccount.provider == (provider or "generic"),
                EmployerAccount.employer_domain == employer_domain,
            )
        )
    ).scalar_one_or_none()


async def upsert_employer_account(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    provider: str,
    employer_domain: str,
    account_email: str,
    login_status: str = "known",
    last_login_at: datetime | None = None,
    metadata_json: dict | None = None,
) -> EmployerAccount:
    """Create or update employer account memory."""

    existing = await get_employer_account(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        provider=provider,
        employer_domain=employer_domain,
    )
    if existing is None:
        existing = EmployerAccount(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=(provider or "generic"),
            employer_domain=employer_domain,
            account_email=account_email,
            login_status=login_status,
            last_login_at=last_login_at,
            metadata_json=metadata_json or {},
        )
        db.add(existing)
        return existing
    existing.account_email = account_email
    existing.login_status = login_status
    existing.last_login_at = last_login_at or existing.last_login_at or datetime.now(UTC)
    existing.metadata_json = {**(existing.metadata_json or {}), **(metadata_json or {})}
    return existing


def split_browser_agent_resume_response(response_data: dict | None) -> tuple[dict, dict]:
    """Split durable resume payload from transient secrets."""

    payload = dict(response_data or {})
    durable = {key: value for key, value in payload.items() if key not in _TRANSIENT_SECRET_FIELDS}
    secrets = {key: value for key, value in payload.items() if key in _TRANSIENT_SECRET_FIELDS and str(value or "").strip()}
    return durable, secrets


async def cache_browser_agent_resume_secrets(run_id: UUID, secrets: dict[str, str]) -> None:
    """Persist transient account/session secrets in Redis with a short TTL."""

    if not secrets:
        return
    try:
        await get_redis().set(
            f"browser-agent:v1:resume-secrets:{run_id}",
            json.dumps(secrets),
            ex=max(60, int(settings.BROWSER_AGENT_V1_RESUME_SECRET_TTL_SECONDS)),
        )
    except Exception:
        return


async def load_browser_agent_resume_secrets(run_id: UUID) -> dict[str, str]:
    """Load transient account/session secrets for a resumed run."""

    try:
        raw = await get_redis().get(f"browser-agent:v1:resume-secrets:{run_id}")
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if str(value or "").strip()}


async def clear_browser_agent_resume_secrets(run_id: UUID) -> None:
    """Remove transient account/session secrets after they are no longer needed."""

    try:
        await get_redis().delete(f"browser-agent:v1:resume-secrets:{run_id}")
    except Exception:
        return
