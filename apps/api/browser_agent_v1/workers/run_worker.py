"""ARQ worker for Browser Agent V1 run execution."""

from __future__ import annotations

from typing import Any
from uuid import UUID

try:
    from arq.connections import RedisSettings
except ModuleNotFoundError:  # pragma: no cover - test/import fallback
    class RedisSettings:  # type: ignore[override]
        @classmethod
        def from_dsn(cls, _dsn: str):
            return cls()

from browser_agent_v1.orchestration.service import execute_run_by_id
from core.arq_queues import QUEUE_BROWSER_AGENT_V1
from core.config import settings
from core.worker_metrics import start_worker_metrics_server
from db.session import AsyncSessionFactory


async def run_browser_agent_v1_task(ctx: dict[str, Any], run_id: str, tenant_id: str, user_id: str) -> dict[str, Any]:
    """Worker entrypoint for one browser-agent run."""

    async with AsyncSessionFactory() as db:
        run = await execute_run_by_id(
            db,
            run_id=UUID(run_id),
            tenant_id=UUID(tenant_id),
            user_id=UUID(user_id),
        )
    return {"run_id": run_id, "status": getattr(run, "status", "unknown")}


async def startup(ctx: dict[str, Any]) -> None:
    """Expose Prometheus metrics for the Browser Agent worker."""

    ctx["metrics_port"] = start_worker_metrics_server(int(settings.BROWSER_AGENT_V1_WORKER_METRICS_PORT))


class WorkerSettings:
    """ARQ worker settings for Browser Agent V1."""

    functions = [run_browser_agent_v1_task]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    queue_name = QUEUE_BROWSER_AGENT_V1
