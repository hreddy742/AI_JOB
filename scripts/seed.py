"""Seed database with sample development data."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from db.models.chat_session import ChatSession
from db.models.enums import ChatModeEnum, PlanEnum, ReferralStatusEnum, RoleEnum
from db.models.job import Job
from db.models.referral import ReferralSuggestion
from db.models.resume import Resume
from db.models.tenant import Tenant
from db.models.user import User
from db.models.user_profile import UserProfile
from db.session import AsyncSessionFactory


async def seed() -> None:
    """Insert baseline tenant/user/profile plus sample chat and referral records."""

    async with AsyncSessionFactory() as db:
        existing = await db.execute(select(Tenant).where(Tenant.name == "Demo Tenant"))
        tenant = existing.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="Demo Tenant", plan=PlanEnum.pro)
            db.add(tenant)
            await db.flush()

        user_q = await db.execute(select(User).where(User.email == "demo@apexapply.dev"))
        user = user_q.scalar_one_or_none()
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email="demo@apexapply.dev",
                password_hash="$2b$12$EXAMPLEHASHEDPASSWORDSTRINGPLACEHOLDER",
                role=RoleEnum.admin,
            )
            db.add(user)
            await db.flush()

        profile_q = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = profile_q.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(
                user_id=user.id,
                tenant_id=tenant.id,
                first_name="Alex",
                last_name="Rivera",
                phone="+1-555-0100",
                linkedin_url="https://linkedin.com/in/alexrivera",
                github_url="https://github.com/alexrivera",
                current_location="New York",
                work_authorization="h1b",
                target_roles=["Software Engineer", "Backend Engineer"],
                target_locations=["Remote", "New York"],
                target_salary_min=120000,
                target_salary_max=180000,
                years_experience=6,
                summary_bio="Backend engineer focused on Python and distributed systems.",
                headline="Senior Python Engineer | 6 YOE",
            )
            db.add(profile)
            await db.flush()

        job_q = await db.execute(select(Job).where(Job.source == "seed", Job.source_id == "seed-job-1"))
        job = job_q.scalar_one_or_none()
        if job is None:
            job = Job(
                tenant_id=tenant.id,
                source="seed",
                source_id="seed-job-1",
                fingerprint="seedseedseedseedseedseedseedseed",
                title="Senior Backend Engineer",
                company="Acme Cloud",
                description="Design resilient Python microservices and APIs.",
                url="https://example.com/jobs/seed-job-1",
                location_city="New York",
                location_country="US",
                remote=True,
                sponsorship_score=0.7,
                tags=["python", "fastapi", "postgres"],
                typesense_synced=False,
            )
            db.add(job)
            await db.flush()

        resume_q = await db.execute(select(Resume).where(Resume.user_id == user.id, Resume.version == 1))
        resume = resume_q.scalar_one_or_none()
        if resume is None:
            resume = Resume(
                user_id=user.id,
                tenant_id=tenant.id,
                version=1,
                original_text="Senior Python engineer with strong SQL and API design experience.",
                parsed_json={"skills": ["Python", "SQL", "FastAPI"]},
                embedding_id="seed-resume-1",
                file_path=f"{tenant.id}/{user.id}/resume-v1.txt",
            )
            db.add(resume)
            await db.flush()

        chat_q = await db.execute(select(ChatSession).where(ChatSession.user_id == user.id, ChatSession.title == "Interview Prep - Acme Cloud"))
        chat = chat_q.scalar_one_or_none()
        if chat is None:
            chat = ChatSession(
                user_id=user.id,
                tenant_id=tenant.id,
                title="Interview Prep - Acme Cloud",
                mode=ChatModeEnum.interview_prep,
                job_id=job.id,
                resume_id=resume.id,
                messages=[
                    {"role": "user", "content": "Help me prep for this backend role", "timestamp": datetime.now(UTC).isoformat()},
                    {"role": "assistant", "content": "Start with API design and concurrency examples from your resume.", "timestamp": datetime.now(UTC).isoformat()},
                ],
            )
            db.add(chat)

        ref_q = await db.execute(select(ReferralSuggestion).where(ReferralSuggestion.user_id == user.id, ReferralSuggestion.company == "Acme Cloud"))
        existing_ref = ref_q.scalar_one_or_none()
        if existing_ref is None:
            db.add(
                ReferralSuggestion(
                    user_id=user.id,
                    tenant_id=tenant.id,
                    job_id=job.id,
                    company="Acme Cloud",
                    contact_name="Jane Doe",
                    contact_title="Bio hint - not verified",
                    contact_source="github",
                    contact_url="https://github.com/janedoe",
                    inferred_email="jane.doe@acmecloud.com",
                    email_pattern="firstname.lastname",
                    confidence_score=0.73,
                    discovery_method="github_api",
                    is_verified=False,
                    status=ReferralStatusEnum.pending,
                )
            )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
