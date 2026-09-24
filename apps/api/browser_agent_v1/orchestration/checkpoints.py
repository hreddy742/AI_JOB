"""Checkpoint helpers for Browser Agent V1."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from browser_agent_v1.perception import PageSignals
from browser_agent_v1.repository.runs import create_snapshot
from db.models.browser_agent_run import BrowserAgentRun
from sqlalchemy.ext.asyncio import AsyncSession


async def persist_snapshot(
    db: AsyncSession,
    *,
    run: BrowserAgentRun,
    page_title: str | None,
    signals: PageSignals,
    planner_context: dict[str, Any],
) -> None:
    """Persist one resumable snapshot for the run."""

    await create_snapshot(
        db,
        run=run,
        state=run.current_state,
        current_url=run.current_url,
        page_title=page_title,
        signals=asdict(signals),
        planner_context=planner_context,
    )
