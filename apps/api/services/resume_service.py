"""Resume service layer and tailoring orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import chromadb
import redis.asyncio as redis
from fastapi import HTTPException, UploadFile, status
from minio import Minio
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from docx import Document

from agents.resume_graph import TailoringState, compiled_graph
from core.config import settings
from core.dependencies import apply_tenant_rls, apply_user_rls
from core.security import TokenPayload
from db.models.job import Job
from db.models.resume_parsed_data import ResumeParsedData
from db.models.resume import Resume, TailoredResume
from db.models.resume_review import ResumeReview
from db.models.resume_version import ResumeVersion
from db.session import AsyncSessionFactory
from schemas.resume import CoverLetterRequest, ResumeResponse, TailoredResumeResponse
from services.autofill_service import build_autofill_profile as build_autofill_profile_service
from services.cover_letter_service import create_cover_letter, get_cover_letter
from services.resume_builder_service import build_resume_from_wizard
from services.resume_editor_service import edit_docx_resume, improve_bullet, restore_resume_version, save_version
from services.embedding_service import store_resume_embedding
from services.resume_parser import upload_resume as parser_upload_resume
from services.resume_reviewer_service import generate_review

logger = logging.getLogger(__name__)

_LOCAL_TASKS: dict[str, dict[str, Any]] = {}
_TASK_LOCK = asyncio.Lock()


def _redis_client() -> redis.Redis:
    """Create async Redis client."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def _sanitize_text(value: str) -> str:
    """Normalize extracted text before storing in DB."""

    text = value.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF bytes."""

    reader = PdfReader(BytesIO(content))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return _sanitize_text("\n\n".join(chunks))


def _extract_docx_text(content: bytes) -> str:
    """Extract text from DOCX bytes."""

    document = Document(BytesIO(content))
    chunks: list[str] = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return _sanitize_text("\n".join(chunks))


def _extract_text(content: bytes, filename: str) -> str:
    """Extract resume text from upload bytes."""

    extension = Path(filename.lower()).suffix
    try:
        if extension == ".pdf":
            return _extract_pdf_text(content)
        if extension == ".docx":
            return _extract_docx_text(content)
    except Exception as exc:  # pragma: no cover - format-specific parsing failures
        logger.warning("Resume extraction failed for %s: %s", filename, exc)
        return ""

    # Plain-text fallback for .txt/.md and unknown file types.
    return _sanitize_text(content.decode("utf-8", errors="ignore"))


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in {"\n", "\r", "\t"})
    return printable / len(text)


async def _store_resume_embedding_async(resume_id: UUID, text: str) -> None:
    """Store resume embedding in background."""

    chroma = chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT)
    await store_resume_embedding(str(resume_id), text, chroma)


async def upload_resume(db: AsyncSession, token: TokenPayload, file: UploadFile) -> ResumeResponse:
    """Persist uploaded resume and enqueue embedding generation."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    resume = await parser_upload_resume(file=file, user_id=user_id, tenant_id=tenant_id, label="My Resume", db=db)
    return ResumeResponse.model_validate(resume)


async def list_resumes(db: AsyncSession, token: TokenPayload) -> list[ResumeResponse]:
    """List active resumes for current user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id, Resume.tenant_id == tenant_id, Resume.is_active.is_(True))
    )
    return [ResumeResponse.model_validate(item) for item in result.scalars().all()]


async def get_resume(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> ResumeResponse:
    """Fetch one resume by ID for current user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return ResumeResponse.model_validate(resume)


async def delete_resume(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> None:
    """Soft-delete a resume by setting is_active=false."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    resume.is_active = False
    await db.commit()


async def _set_task_status(task_id: str, payload: dict[str, Any]) -> None:
    """Store tailoring task status in memory and Redis."""

    async with _TASK_LOCK:
        _LOCAL_TASKS[task_id] = payload

    redis_client = _redis_client()
    await redis_client.set(f"resume:tailor:task:{task_id}", json.dumps(payload), ex=3600)


async def run_tailoring_pipeline(task_id: str, user_id: UUID, tenant_id: UUID, resume_id: UUID, job_id: UUID) -> None:
    """Execute full tailoring graph and persist result."""

    await _set_task_status(task_id, {"status": "running", "task_id": task_id})
    async with AsyncSessionFactory() as db:
        await apply_tenant_rls(db, tenant_id)
        await apply_user_rls(db, user_id)

        resume_res = await db.execute(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id)
        )
        resume = resume_res.scalar_one_or_none()

        job_res = await db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
        job = job_res.scalar_one_or_none()

        if resume is None or job is None:
            await _set_task_status(task_id, {"status": "failed", "task_id": task_id, "error": "resume or job not found"})
            return

        parsed = (
            await db.execute(select(ResumeParsedData).where(ResumeParsedData.resume_id == resume_id, ResumeParsedData.user_id == user_id))
        ).scalar_one_or_none()

        initial_state: TailoringState = {
            "original_resume_text": resume.original_text,
            "parsed_resume": {
                "skills_all": (parsed.skills_all if parsed else []),
                "work_experience": (parsed.work_experience if parsed else []),
            },
            "job_description": job.description or "",
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "resume_id": str(resume_id),
            "job_id": str(job_id),
            "target_company": job.company,
            "target_title": job.title,
            "jd_analysis": {},
            "tailored_text": "",
            "diff_log": [],
            "review_report": {},
            "violations": [],
            "ats_score": 0.0,
            "quality_score": 0.0,
            "supervisor_decision": "",
            "retry_count": 0,
            "retry_notes": "",
            "final_tailored_text": "",
            "error": None,
        }

        result = await compiled_graph.ainvoke(initial_state)

        tailored = TailoredResume(
            user_id=user_id,
            tenant_id=tenant_id,
            job_id=job_id,
            source_resume_id=resume_id,
            job_title_target=job.title,
            company_target=job.company,
            tailored_text=result.get("final_tailored_text") or result.get("tailored_text") or resume.original_text,
            diff_log=result.get("diff_log") or [],
            ats_score=float(result.get("ats_score") or 0.0),
            quality_score=float(result.get("quality_score") or 0.0),
            review_report=result.get("review_report") or {},
            supervisor_decision=result.get("supervisor_decision"),
            violation_count=len(result.get("violations") or []),
            reviewer_score=float(result.get("quality_score") or 0.0),
            supervisor_approved=result.get("supervisor_decision") == "APPROVED",
            violations=result.get("violations") or [],
            retry_count=int(result.get("retry_count") or 0),
            generation_model=settings.WRITER_MODEL,
            status=("approved" if result.get("supervisor_decision") == "APPROVED" else "rejected"),
        )
        db.add(tailored)
        await db.commit()
        await db.refresh(tailored)

    await _set_task_status(
        task_id,
        {
            "status": "completed",
            "task_id": task_id,
            "tailored_resume_id": str(tailored.id),
            "supervisor_decision": result.get("supervisor_decision"),
            "reviewer_score": result.get("quality_score"),
        },
    )


async def create_tailoring_task(db: AsyncSession, token: TokenPayload, resume_id: UUID, job_id: UUID) -> str:
    """Create and dispatch a background tailoring task."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    task_id = str(uuid4())
    await _set_task_status(task_id, {"status": "queued", "task_id": task_id})
    asyncio.create_task(run_tailoring_pipeline(task_id, user_id, tenant_id, resume_id, job_id))
    return task_id


async def get_tailoring_task_status(task_id: str) -> dict[str, Any]:
    """Return current tailoring task status."""

    async with _TASK_LOCK:
        local = _LOCAL_TASKS.get(task_id)
    if local is not None:
        return local

    redis_client = _redis_client()
    raw = await redis_client.get(f"resume:tailor:task:{task_id}")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"status": "unknown", "task_id": task_id}


async def list_tailored_resumes(db: AsyncSession, token: TokenPayload, source_resume_id: UUID) -> list[TailoredResumeResponse]:
    """List tailored resumes generated from a source resume."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    result = await db.execute(
        select(TailoredResume)
        .where(
            TailoredResume.source_resume_id == source_resume_id,
            TailoredResume.user_id == user_id,
            TailoredResume.tenant_id == tenant_id,
        )
        .order_by(TailoredResume.created_at.desc())
    )
    return [TailoredResumeResponse.model_validate(item) for item in result.scalars().all()]


async def get_tailored_resume(db: AsyncSession, token: TokenPayload, tailored_id: UUID) -> TailoredResumeResponse:
    """Fetch one tailored resume for the authenticated user."""

    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)

    result = await db.execute(
        select(TailoredResume).where(
            TailoredResume.id == tailored_id,
            TailoredResume.user_id == user_id,
            TailoredResume.tenant_id == tenant_id,
        )
    )
    tailored = result.scalar_one_or_none()
    if tailored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored resume not found")
    return TailoredResumeResponse.model_validate(tailored)


async def export_tailored_resume_pdf(db: AsyncSession, token: TokenPayload, tailored_id: UUID) -> BytesIO:
    """Export tailored resume text as a minimal PDF stream."""

    tailored = await get_tailored_resume(db, token, tailored_id)
    text = tailored.tailored_text.replace("(", "[").replace(")", "]")[:5000]
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << >> >> endobj\n"
        f"4 0 obj << /Length {len(text) + 30} >> stream\nBT /F1 12 Tf 40 740 Td ({text}) Tj ET\nendstream endobj\n"
        "xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n"
        "0000000118 00000 n \n0000000220 00000 n \n"
        "trailer << /Root 1 0 R /Size 5 >>\nstartxref\n330\n%%EOF"
    )
    return BytesIO(pdf.encode("latin-1", errors="ignore"))


def _minio_client() -> Minio:
    secure = settings.MINIO_ENDPOINT.startswith("https://")
    endpoint = settings.MINIO_ENDPOINT.replace("https://", "").replace("http://", "")
    return Minio(endpoint, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=secure)


async def get_resume_download_url(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> str:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None or not resume.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    client = _minio_client()
    return client.presigned_get_object(settings.MINIO_BUCKET, resume.file_path, expires=timedelta(minutes=15))


async def update_resume_metadata(db: AsyncSession, token: TokenPayload, resume_id: UUID, label: str | None, is_primary: bool | None) -> ResumeResponse:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if label is not None:
        resume.label = label[:100]
    if is_primary is not None:
        if is_primary:
            others = (
                await db.execute(
                    select(Resume).where(Resume.user_id == user_id, Resume.tenant_id == tenant_id, Resume.id != resume_id)
                )
            ).scalars().all()
            for row in others:
                row.is_primary = False
        resume.is_primary = is_primary
    await db.commit()
    await db.refresh(resume)
    return ResumeResponse.model_validate(resume)


async def permanent_delete_resume(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> None:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.file_path:
        client = _minio_client()
        try:
            client.remove_object(settings.MINIO_BUCKET, resume.file_path)
        except Exception:
            logger.warning("Failed to remove MinIO object %s", resume.file_path)
    await db.delete(resume)
    await db.commit()


async def generate_cover_letter_for_resume(
    db: AsyncSession,
    token: TokenPayload,
    resume_id: UUID,
    payload: CoverLetterRequest,
):
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    return await create_cover_letter(db, user_id, tenant_id, resume_id, payload.job_id, payload.tone, payload.hiring_manager_name)


async def get_or_generate_review(db: AsyncSession, token: TokenPayload, resume_id: UUID, force_new: bool) -> ResumeReview:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    return await generate_review(db, user_id, tenant_id, resume_id, force_new=force_new)


async def list_resume_versions(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> list[ResumeVersion]:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    rows = (
        await db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id, ResumeVersion.user_id == user_id)
            .order_by(ResumeVersion.version_number.desc())
        )
    ).scalars().all()
    return rows


async def restore_resume_version_number(db: AsyncSession, token: TokenPayload, resume_id: UUID, version_number: int) -> ResumeResponse:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    resume = await restore_resume_version(db, user_id, tenant_id, resume_id, version_number)
    return ResumeResponse.model_validate(resume)


async def edit_resume_content(
    db: AsyncSession,
    token: TokenPayload,
    resume_id: UUID,
    original_value: str,
    new_value: str,
    change_summary: str,
) -> ResumeResponse:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.file_type == "docx":
        resume = await edit_docx_resume(db, user_id, tenant_id, resume_id, original_value, new_value, change_summary)
        return ResumeResponse.model_validate(resume)
    resume.original_text = (resume.original_text or "").replace(original_value, new_value, 1)
    resume.raw_text = resume.original_text
    await save_version(db, resume.id, user_id, resume.original_text, change_summary)
    await db.commit()
    await db.refresh(resume)
    return ResumeResponse.model_validate(resume)


async def improve_bullet_text(
    db: AsyncSession,
    token: TokenPayload,
    resume_id: UUID,
    original: str,
    target_role: str | None,
) -> dict[str, str]:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)
    await apply_user_rls(db, user_id)
    resume = (
        await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id, Resume.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    suggestion = await improve_bullet(original, "past", "", "", target_role or "")
    return {"original": original, "suggestion": suggestion}


async def build_resume(db: AsyncSession, token: TokenPayload, payload: dict[str, Any]) -> ResumeResponse:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    resume = await build_resume_from_wizard(db, user_id, tenant_id, payload)
    return ResumeResponse.model_validate(resume)


async def get_resume_autofill_profile(db: AsyncSession, token: TokenPayload, resume_id: UUID) -> dict[str, Any]:
    user_id = UUID(token.sub)
    tenant_id = UUID(token.tenant_id)
    return await build_autofill_profile_service(db, user_id, tenant_id, resume_id)
