"""Async AI utility routes for frontend polling flows."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.outreach_graph import compiled_outreach_graph
from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls, get_current_token, get_db
from core.llm_telemetry import ollama_chat
from core.redis import get_redis
from core.security import TokenPayload
from db.models.contact import Contact
from db.models.job import Job
from db.models.resume import Resume
from db.models.user_profile import UserProfile
from db.session import AsyncSessionFactory

router = APIRouter(prefix="/ai", tags=["ai"])


def _extract_terms(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{2,}", text or "")
    seen: list[str] = []
    for word in words:
        value = word.strip()
        if value.lower() in {item.lower() for item in seen}:
            continue
        seen.append(value)
        if len(seen) >= 8:
            break
    return seen


def _fallback_cover_letter(job_description: str, resume_text: str) -> str:
    terms = _extract_terms(f"{job_description} {resume_text}")
    focus = ", ".join(terms[:3]) if terms else "the role requirements"
    return (
        "Dear Hiring Team,\n\n"
        f"I am interested in this opportunity and believe my background aligns well with {focus}. "
        "My experience includes building production software systems, collaborating across teams, and delivering reliable results.\n\n"
        "I would welcome the chance to discuss how I can contribute to your team.\n\n"
        "Best regards,"
    )


async def _set_task(task_id: str, payload: dict) -> None:
    await get_redis().set(f"ai:task:{task_id}", json.dumps(payload), ex=3600)


async def _run_interview_generation(task_id: str, job_description: str) -> None:
    await _set_task(task_id, {"task_id": task_id, "status": "running"})
    questions: list[str]
    try:
        payload = await ollama_chat(
            flow="interview_question_generation",
            model=settings.CREATIVE_LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate 5 role-specific interview questions from the job description. "
                        "Return ONLY valid JSON as {\"questions\": [\"...\"]}."
                    ),
                },
                {"role": "user", "content": job_description or "Software engineering role"},
            ],
            output_format="json",
            stream=False,
            timeout_s=90.0,
            options={"temperature": 0.4},
        )
        content = payload.get("message", {}).get("content", "{}")
        parsed = content if isinstance(content, dict) else json.loads(content)
        raw_questions = parsed.get("questions") if isinstance(parsed, dict) else None
        questions = [str(item).strip() for item in (raw_questions or []) if str(item).strip()][:5]
    except Exception:
        questions = []

    if not questions:
        terms = _extract_terms(job_description)
        lead = terms[:4] or ["system design", "collaboration", "debugging", "delivery"]
        questions = [
            f"Walk me through a project where you used {lead[0]}.",
            f"What tradeoffs would you consider when working with {lead[1] if len(lead) > 1 else 'this stack'}?",
            f"Describe a difficult bug or failure you handled related to {lead[2] if len(lead) > 2 else 'the role requirements'}.",
            f"How would you prioritize work and communicate risk in a role focused on {lead[3] if len(lead) > 3 else 'execution'}?",
            "Tell me about a time you had to learn something quickly to deliver on a deadline.",
        ]

    await _set_task(
        task_id,
        {
            "task_id": task_id,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "questions": questions,
        },
    )


async def _run_cover_letter_generation(
    task_id: str,
    user_id: str,
    tenant_id: str,
    payload: dict,
) -> None:
    await _set_task(task_id, {"task_id": task_id, "status": "running"})
    try:
        async with AsyncSessionFactory() as db:
            tenant_uuid = UUID(tenant_id)
            user_uuid = UUID(user_id)
            await apply_tenant_rls(db, tenant_uuid)
            await apply_user_rls(db, user_uuid)

            resume_text = str(payload.get("resume_text") or "").strip()
            resume_id = str(payload.get("resume_id") or "").strip()
            job_id = str(payload.get("job_id") or "").strip()
            job_description = str(payload.get("job_description") or "").strip()
            if resume_id:
                try:
                    resume = (
                        await db.execute(
                            select(Resume).where(Resume.id == UUID(resume_id), Resume.user_id == user_uuid, Resume.tenant_id == tenant_uuid)
                        )
                    ).scalar_one_or_none()
                    if resume is not None and not resume_text:
                        resume_text = resume.original_text or ""
                except ValueError:
                    pass
            if job_id and not job_description:
                try:
                    job = (await db.execute(select(Job).where(Job.id == UUID(job_id), Job.tenant_id == tenant_uuid))).scalar_one_or_none()
                    if job is not None:
                        job_description = job.description or ""
                except ValueError:
                    pass

        prompt = (
            "Write a concise, professional cover letter in plain text. "
            "Use only the provided facts. Do not invent companies, metrics, or experience.\n\n"
            f"Resume:\n{resume_text[:8000]}\n\nJob Description:\n{job_description[:4000]}"
        )
        llm_payload = await ollama_chat(
            flow="cover_letter_generation",
            model=settings.CREATIVE_LLM_MODEL,
            messages=[{"role": "system", "content": prompt}],
            stream=False,
            timeout_s=120.0,
            options={"temperature": 0.35},
        )
        content = str(llm_payload.get("message", {}).get("content", "") or "").strip()
        if not content:
            content = _fallback_cover_letter(job_description, resume_text)
        await _set_task(
            task_id,
            {
                "task_id": task_id,
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "content": content,
            },
        )
    except Exception as exc:
        await _set_task(
            task_id,
            {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )


async def _run_outreach_draft_generation(
    task_id: str,
    user_id: str,
    tenant_id: str,
    payload: dict,
) -> None:
    await _set_task(task_id, {"task_id": task_id, "status": "running"})
    try:
        async with AsyncSessionFactory() as db:
            tenant_uuid = UUID(tenant_id)
            user_uuid = UUID(user_id)
            await apply_tenant_rls(db, tenant_uuid)
            await apply_user_rls(db, user_uuid)

            contact_payload = {"name": "", "company": "", "title": ""}
            raw_contact_id = str(payload.get("contact_id") or "").strip()
            if raw_contact_id:
                try:
                    contact = (
                        await db.execute(
                            select(Contact).where(Contact.id == UUID(raw_contact_id), Contact.user_id == user_uuid, Contact.tenant_id == tenant_uuid)
                        )
                    ).scalar_one_or_none()
                    if contact is not None:
                        contact_payload = {"name": contact.name, "company": contact.company, "title": contact.title}
                except ValueError:
                    contact_payload["name"] = raw_contact_id

            job_payload = None
            raw_job_id = str(payload.get("job_id") or "").strip()
            if raw_job_id:
                try:
                    job = (await db.execute(select(Job).where(Job.id == UUID(raw_job_id), Job.tenant_id == tenant_uuid))).scalar_one_or_none()
                    if job is not None:
                        job_payload = {"title": job.title, "company": job.company, "description": job.description}
                except ValueError:
                    job_payload = {"title": raw_job_id, "company": "", "description": ""}

            profile = (
                await db.execute(select(UserProfile).where(UserProfile.user_id == user_uuid, UserProfile.tenant_id == tenant_uuid))
            ).scalar_one_or_none()
            resume = (
                await db.execute(
                    select(Resume)
                    .where(Resume.user_id == user_uuid, Resume.tenant_id == tenant_uuid, Resume.is_active.is_(True))
                    .order_by(Resume.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        state = {
            "contact": contact_payload,
            "job": job_payload,
            "resume_summary": (resume.original_text[:1000] if resume else ""),
            "user_profile": {
                "first_name": (profile.first_name if profile else ""),
                "last_name": (profile.last_name if profile else ""),
                "headline": (profile.headline if profile else ""),
                "tone": str(payload.get("tone") or "professional"),
            },
            "draft_text": "",
            "compliance_report": {},
        }
        result = await compiled_outreach_graph.ainvoke(state)
        await _set_task(
            task_id,
            {
                "task_id": task_id,
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "draft_text": result.get("draft_text") or "",
                "compliance_report": result.get("compliance_report") or {},
            },
        )
    except Exception as exc:
        await _set_task(
            task_id,
            {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )


@router.post("/interview-questions")
async def create_interview_questions_task(payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Queue interview question generation from freeform JD text."""

    task_id = str(uuid4())
    await _set_task(task_id, {"task_id": task_id, "status": "queued"})
    background_tasks.add_task(_run_interview_generation, task_id, str(payload.get("job_description") or ""))
    return {"task_id": task_id}


@router.post("/cover-letter")
async def generate_cover_letter(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue creative cover-letter generation and return a polling task id."""

    await apply_tenant_rls(db, UUID(current_user.tenant_id))
    await apply_user_rls(db, UUID(current_user.sub))
    task_id = str(uuid4())
    await _set_task(task_id, {"task_id": task_id, "status": "queued"})
    background_tasks.add_task(_run_cover_letter_generation, task_id, current_user.sub, current_user.tenant_id, dict(payload or {}))
    return {"task_id": task_id}


@router.post("/outreach-draft")
async def generate_outreach_draft(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue outreach draft generation and return a polling task id."""

    await apply_tenant_rls(db, UUID(current_user.tenant_id))
    await apply_user_rls(db, UUID(current_user.sub))
    task_id = str(uuid4())
    await _set_task(task_id, {"task_id": task_id, "status": "queued"})
    background_tasks.add_task(_run_outreach_draft_generation, task_id, current_user.sub, current_user.tenant_id, dict(payload or {}))
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
async def get_ai_task(task_id: str) -> dict:
    """Fetch AI task state."""

    raw = await get_redis().get(f"ai:task:{task_id}")
    if raw:
        return json.loads(raw)

    tailoring_raw = await get_redis().get(f"resume:tailor:task:{task_id}")
    if not tailoring_raw:
        return {"task_id": task_id, "status": "not_found"}

    parsed = json.loads(tailoring_raw)
    checkpoint_raw = await get_redis().get(f"resume:tailor:checkpoint:{task_id}")
    if checkpoint_raw:
        checkpoint = json.loads(checkpoint_raw)
        if isinstance(checkpoint, dict):
            parsed["checkpoint"] = checkpoint
            parsed["phase"] = checkpoint.get("phase")
            parsed["progress"] = checkpoint.get("progress")
    return parsed
