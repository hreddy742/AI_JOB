"""Tailoring worker entrypoints."""

from __future__ import annotations

from uuid import UUID

from services.resume_service import run_tailoring_pipeline


async def tailor_resume_task(
    ctx: dict,
    task_id: str,
    user_id: str,
    tenant_id: str,
    resume_id: str,
    job_id: str,
) -> dict[str, str]:
    """Run one resume tailoring task from queue payload."""

    await run_tailoring_pipeline(
        task_id=task_id,
        user_id=UUID(user_id),
        tenant_id=UUID(tenant_id),
        resume_id=UUID(resume_id),
        job_id=UUID(job_id),
    )
    return {"task_id": task_id, "status": "completed"}


class WorkerSettings:
    """ARQ worker settings for tailoring jobs."""

    functions = [tailor_resume_task]
