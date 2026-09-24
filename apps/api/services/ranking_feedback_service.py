"""Adaptive ranking feedback foundation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ranking_feedback import RankingFeedback


async def record_ranking_feedback(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    job_id: UUID,
    event_type: str,
    value: str | None = None,
) -> None:
    db.add(
        RankingFeedback(
            tenant_id=tenant_id,
            user_id=user_id,
            job_id=job_id,
            event_type=(event_type or "unknown").strip().lower(),
            value=(value or "").strip() or None,
        )
    )


async def get_user_feedback_summary(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> dict[str, int]:
    rows = (
        await db.execute(
            select(RankingFeedback.event_type, func.count())
            .where(RankingFeedback.tenant_id == tenant_id, RankingFeedback.user_id == user_id)
            .group_by(RankingFeedback.event_type)
        )
    ).all()
    return {str(event): int(count) for event, count in rows}


async def get_user_job_feedback_scores(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> dict[str, float]:
    """Aggregate per-job feedback into deterministic preference scores."""

    rows = (
        await db.execute(
            select(RankingFeedback.job_id, RankingFeedback.event_type, func.count())
            .where(RankingFeedback.tenant_id == tenant_id, RankingFeedback.user_id == user_id)
            .group_by(RankingFeedback.job_id, RankingFeedback.event_type)
        )
    ).all()
    # Conservative, explainable weights. Unknown events contribute zero.
    weights = {
        "save": 1.0,
        "unsave": -1.2,
        "open": 0.2,
        "apply_click": 0.4,
    }
    scores: dict[str, float] = {}
    for job_id, event_type, count in rows:
        score = float(weights.get(str(event_type), 0.0)) * float(count or 0)
        if score == 0:
            continue
        key = str(job_id)
        scores[key] = scores.get(key, 0.0) + score
    return scores
