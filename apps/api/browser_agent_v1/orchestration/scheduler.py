"""Queue scheduling for Browser Agent V1."""

from __future__ import annotations

from core.task_queue import enqueue_arq_job


async def enqueue_run(run_id: str, *, tenant_id: str, user_id: str, queue_name: str) -> None:
    """Enqueue a browser-agent run for worker execution."""

    await enqueue_arq_job(
        "run_browser_agent_v1_task",
        run_id,
        tenant_id,
        user_id,
        queue_name=queue_name,
        job_id=f"browser-agent-v1:{run_id}",
    )
