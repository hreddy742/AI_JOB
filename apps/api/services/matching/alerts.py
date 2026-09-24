"""Alert budget and dedup-window enforcement."""

from __future__ import annotations

from datetime import UTC, date, datetime

from core.config import settings
from core.redis import get_redis
from services.alert_budget_service import ALERT_DEDUP_WINDOW_SECONDS, get_user_alert_budget

redis = get_redis()


async def should_send_alert(user_id: str, job_id: str, *, redis_client=None) -> bool:
    """Return True only when user is in budget and job is not recently alerted."""

    client = redis_client or redis
    budget_key = f"alert_budget:{user_id}:{date.today().isoformat()}"
    count = await client.incr(budget_key)
    if count == 1:
        midnight = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC).timestamp() + 86400
        ttl = max(int(midnight - datetime.now(UTC).timestamp()), 1)
        await client.expire(budget_key, ttl)
    effective_budget = await get_user_alert_budget(user_id) or settings.ALERT_BUDGET_PER_DAY
    if count > int(effective_budget):
        return False

    dedup_key = f"alerted:{user_id}:{job_id}"
    if await client.exists(dedup_key):
        return False
    await client.setex(dedup_key, ALERT_DEDUP_WINDOW_SECONDS, "1")
    return True
