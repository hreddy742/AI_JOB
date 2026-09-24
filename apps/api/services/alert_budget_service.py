"""Alert budget and dedup-window helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text

from core.config import settings
from db.session import AsyncSessionFactory

ALERT_DEDUP_WINDOW_SECONDS = 72 * 3600


async def get_user_alert_budget(user_id: str) -> int | None:
    """Return the user's configured daily alert budget."""

    sql = text("SELECT alert_budget_per_day FROM user_profiles WHERE user_id = :user_id::uuid")
    async with AsyncSessionFactory() as session:
        row = (await session.execute(sql, {"user_id": user_id})).mappings().first()
    if not row:
        return None
    value = row.get("alert_budget_per_day")
    return int(value) if value is not None else None


async def should_send_alert(redis_client, user_id: str, job_id: str, budget_per_day: int = 10) -> bool:
    """Return whether a job alert can be sent for a user."""

    budget_key = f"alert_budget:{user_id}:{date.today().isoformat()}"
    count = await redis_client.incr(budget_key)
    if count == 1:
        midnight = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC).timestamp() + 86400
        ttl = max(int(midnight - datetime.now(UTC).timestamp()), 1)
        await redis_client.expire(budget_key, ttl)
    effective_budget = await get_user_alert_budget(user_id) or settings.ALERT_BUDGET_PER_DAY or budget_per_day
    if count > int(effective_budget):
        return False

    dedup_key = f"alerted:{user_id}:{job_id}"
    if await redis_client.exists(dedup_key):
        return False
    await redis_client.setex(dedup_key, ALERT_DEDUP_WINDOW_SECONDS, "1")
    return True


def build_alert_policy_snapshot(
    *,
    effective_budget: int | None,
    needs_sponsorship: bool,
    location_type: str,
    min_salary: float | None,
    company: str | None,
    job_remote: bool | None,
    job_salary_max: float | None,
    job_sponsorship_status: str | None,
) -> dict[str, Any]:
    """Return compact policy context for queued alert diagnostics."""

    reasons: list[str] = []
    if needs_sponsorship and str(job_sponsorship_status or "unknown") != "no_sponsor":
        reasons.append("sponsorship-compatible")
    if location_type == "remote" and bool(job_remote):
        reasons.append("matches-remote-preference")
    if min_salary is not None and (job_salary_max is None or float(job_salary_max) >= float(min_salary)):
        reasons.append("meets-salary-target")
    if company:
        reasons.append(f"company:{company}")

    return {
        "effective_budget_per_day": int(effective_budget) if effective_budget is not None else None,
        "dedup_window_hours": ALERT_DEDUP_WINDOW_SECONDS // 3600,
        "reasons": reasons,
    }
