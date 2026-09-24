"""Coverage metrics helpers and dashboard query templates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.redis import get_redis


async def incr_source_metric(source: str, metric: str, value: int = 1) -> None:
    day = datetime.now(UTC).date().isoformat()
    key = f"metrics:coverage:{source}:{day}"
    redis = get_redis()
    await redis.hincrby(key, metric, value)
    await redis.expire(key, 86400 * 30)


async def set_freshness_latency(source: str, seconds: float) -> None:
    day = datetime.now(UTC).date().isoformat()
    key = f"metrics:coverage:{source}:{day}"
    await get_redis().hset(key, mapping={"freshness_latency_seconds": str(max(seconds, 0.0))})


def dashboard_sql_queries() -> dict[str, str]:
    return {
        "jobs_ingested_per_source": """
            SELECT source, date_trunc('hour', ingested_at) AS hour, count(*) AS jobs
            FROM jobs
            WHERE ingested_at >= now() - interval '24 hours'
            GROUP BY source, hour
            ORDER BY hour DESC;
        """.strip(),
        "jobs_failed_per_source": """
            SELECT source,
                   count(*) FILTER (WHERE payload->>'errors' IS NOT NULL) AS failed_runs
            FROM supervisor_logs
            WHERE event_type = 'ingestion_run' AND created_at >= now() - interval '24 hours'
            GROUP BY source;
        """.strip(),
        "duplicate_rate": """
            SELECT source,
                   round(100.0 * sum(CASE WHEN method <> 'new' THEN 1 ELSE 0 END) / nullif(count(*), 0), 2) AS duplicate_pct
            FROM dedup_log
            WHERE created_at >= now() - interval '24 hours'
            GROUP BY source;
        """.strip(),
        "crawler_error_rate": """
            SELECT source,
                   round(100.0 * avg((payload->>'errors')::float), 2) AS avg_errors
            FROM supervisor_logs
            WHERE event_type = 'ingestion_run' AND created_at >= now() - interval '24 hours'
            GROUP BY source;
        """.strip(),
        "freshness_latency": """
            SELECT source,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (ingested_at - posted_at))) AS p95_latency_seconds
            FROM jobs
            WHERE posted_at IS NOT NULL AND ingested_at >= now() - interval '24 hours'
            GROUP BY source;
        """.strip(),
        "queue_lag": """
            SELECT now() AS ts,
                   (SELECT count(*) FROM jobs WHERE typesense_synced = false) AS typesense_backlog;
        """.strip(),
    }


def to_dashboard_payload() -> dict[str, Any]:
    return {"generated_at": datetime.now(UTC).isoformat(), "queries": dashboard_sql_queries()}
