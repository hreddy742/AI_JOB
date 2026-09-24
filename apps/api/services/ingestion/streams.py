"""Reliable Redis Streams producer/consumer helpers for ingestion."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any
from uuid import UUID

from sqlalchemy import text

from adapters.base import NormalizedJob
from core.observability import (
    stream_dlq_total,
    stream_pending_age_seconds,
    stream_queue_lag,
    stream_retries_total,
)
from core.redis import get_redis
from core.dependencies import apply_tenant_rls
from services.ingestion.envelope import Envelope, build_envelope, decode_message, encode_message
from db.session import AsyncSessionFactory
from services.job_service import upsert_job
from services.search_service import get_typesense_client

logger = logging.getLogger(__name__)

RAW_STREAM = "ingestion.raw"
DLQ_STREAM = "ingestion.dlq"
GROUP = "ingest-workers"
MAX_ATTEMPTS = 5
STALE_IDLE_MS = 60_000


def _retry_backoff_seconds(attempt: int) -> float:
    base = min(60.0, 2.0 ** max(attempt, 0))
    return base + random.uniform(0.0, 0.35 * base)


async def ensure_consumer_group() -> None:
    """Create the ingestion consumer group if it does not exist."""

    redis = get_redis()
    try:
        await redis.xgroup_create(RAW_STREAM, GROUP, id="0", mkstream=True)
    except Exception:
        # Group already exists.
        pass


async def push_job_to_stream(job_data: dict[str, Any], source: str) -> None:
    """Push one normalized job payload into the raw ingestion stream envelope."""

    tenant_id = str(job_data.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required for ingestion stream publish")
    envelope = build_envelope(
        tenant_id=tenant_id,
        type="job.ingestion",
        source=source,
        payload=job_data,
        idempotency_key=f"{tenant_id}:{source}:{job_data.get('source_id', '')}",
    )
    await get_redis().xadd(RAW_STREAM, encode_message(envelope), maxlen=50000)


async def _mark_processed_if_first(db: Any, tenant_id: str, stream_name: str, message_id: str) -> bool:
    """Insert idempotency record; return False when already processed."""

    result = await db.execute(
        text(
            """
            INSERT INTO stream_processing_log (tenant_id, stream_name, message_id)
            VALUES (CAST(:tenant_id AS uuid), :stream_name, :message_id)
            ON CONFLICT (tenant_id, stream_name, message_id) DO NOTHING
            RETURNING message_id
            """
        ),
        {"tenant_id": tenant_id, "stream_name": stream_name, "message_id": message_id},
    )
    return result.scalar_one_or_none() is not None


async def process_and_save_job(envelope: Envelope, typesense_client: Any | None = None) -> tuple[bool, bool]:
    """Process one envelope and persist job.

    Returns:
      (inserted, duplicate_message)
    """

    tenant_id = envelope.tenant_id
    async with AsyncSessionFactory() as db:
        await apply_tenant_rls(db, UUID(tenant_id))
        is_first = await _mark_processed_if_first(db, tenant_id, RAW_STREAM, envelope.message_id)
        if not is_first:
            await db.commit()
            return False, True

        payload = dict(envelope.payload)
        payload["tenant_id"] = tenant_id
        job = NormalizedJob.model_validate({**payload, "source": envelope.source})
        was_new = await upsert_job(
            job,
            db,
            typesense_client or get_typesense_client(),
            commit=False,
            trigger_post_save=False,
        )
        await db.commit()
        return was_new, False


async def _send_to_dlq(envelope: Envelope, error: str, redis_msg_id: str) -> None:
    dlq_payload = {
        **envelope.payload,
        "_error": error,
        "_failed_stream_message_id": redis_msg_id,
        "_failed_at": int(time.time()),
    }
    dlq_envelope = build_envelope(
        tenant_id=envelope.tenant_id,
        type=f"{envelope.type}.failed",
        source=envelope.source,
        payload=dlq_payload,
        idempotency_key=envelope.idempotency_key,
        attempt=envelope.attempt,
    )
    await get_redis().xadd(DLQ_STREAM, encode_message(dlq_envelope), maxlen=50000)
    stream_dlq_total.labels(stream=RAW_STREAM, type=envelope.type).inc()


async def reclaim_stale_pending(worker_id: str, min_idle_ms: int = STALE_IDLE_MS, count: int = 50) -> list[tuple[str, dict[str, Any]]]:
    """Reclaim stale pending messages for this consumer using XAUTOCLAIM."""

    redis = get_redis()
    reclaimed: list[tuple[str, dict[str, Any]]] = []
    start = "0-0"
    try:
        while True:
            claim_result = await redis.xautoclaim(RAW_STREAM, GROUP, worker_id, min_idle_ms, start, count=count)
            if not claim_result:
                break
            if len(claim_result) >= 2:
                next_start = claim_result[0]
                messages = claim_result[1] or []
            else:
                break
            for msg_id, fields in messages:
                reclaimed.append((str(msg_id), fields))
            start = str(next_start)
            if not messages:
                break
    except Exception:
        logger.exception("stream_reclaim_failed", extra={"extra": {"stream": RAW_STREAM, "group": GROUP, "worker_id": worker_id}})
    return reclaimed


async def _update_stream_health_metrics() -> None:
    redis = get_redis()
    try:
        lag = await redis.xlen(RAW_STREAM)
        stream_queue_lag.labels(stream=RAW_STREAM).set(float(lag or 0))
    except Exception:
        return
    try:
        pending = await redis.xpending_range(RAW_STREAM, GROUP, min="-", max="+", count=1)
        if pending:
            oldest = pending[0]
            idle_ms = float(oldest.get("time_since_delivered", 0))
            stream_pending_age_seconds.labels(stream=RAW_STREAM, group=GROUP).set(idle_ms / 1000.0)
        else:
            stream_pending_age_seconds.labels(stream=RAW_STREAM, group=GROUP).set(0.0)
    except Exception:
        return


async def process_stream_batch(worker_id: str, count: int = 10, block_ms: int = 1000) -> dict[str, int]:
    """Process and ack one batch with retry, reclaim, idempotency and DLQ."""

    await ensure_consumer_group()
    redis = get_redis()
    reclaimed = await reclaim_stale_pending(worker_id=worker_id, min_idle_ms=STALE_IDLE_MS, count=max(count, 1))
    messages = await redis.xreadgroup(GROUP, worker_id, {RAW_STREAM: ">"}, count=max(count, 1), block=block_ms)
    entries: list[tuple[str, dict[str, Any]]] = []
    for _stream, chunk in messages or []:
        for msg_id, data in chunk:
            entries.append((str(msg_id), data))
    entries.extend(reclaimed)

    if not entries:
        await _update_stream_health_metrics()
        return {"processed": 0, "inserted": 0, "errors": 0}

    inserted = 0
    errors = 0
    processed = 0
    typesense_client = get_typesense_client()
    for redis_msg_id, data in entries:
        processed += 1
        try:
            envelope = decode_message(data)
        except Exception as exc:
            # Backward-compatibility path for legacy payload-only stream messages.
            try:
                if "payload" in data and "source" in data:
                    raw_payload = data.get("payload")
                    payload = raw_payload if isinstance(raw_payload, dict) else json.loads(str(raw_payload))
                    tenant_id = str(payload.get("tenant_id") or "").strip()
                    if tenant_id:
                        envelope = build_envelope(
                            tenant_id=tenant_id,
                            type="job.ingestion",
                            source=str(data.get("source") or "unknown"),
                            payload=payload,
                            idempotency_key=f"legacy:{redis_msg_id}",
                        )
                    else:
                        raise ValueError("legacy payload missing tenant_id")
                else:
                    raise
            except Exception:
                errors += 1
                logger.error("consumer_bad_envelope", extra={"extra": {"message_id": redis_msg_id, "error": str(exc), "stream": RAW_STREAM}})
                # Fail closed: envelope missing tenant_id or malformed -> DLQ for operator inspection.
                fallback = build_envelope(
                    tenant_id=str(data.get("tenant_id") or "00000000-0000-0000-0000-000000000000"),
                    type="unknown",
                    source=str(data.get("source") or "unknown"),
                    payload={"raw_fields": {k: str(v) for k, v in data.items()}},
                    idempotency_key=f"bad:{redis_msg_id}",
                )
                await _send_to_dlq(fallback, f"decode_error:{exc}", redis_msg_id)
                await redis.xack(RAW_STREAM, GROUP, redis_msg_id)
                continue

        trace = {
            "trace_id": envelope.idempotency_key,
            "tenant_id": envelope.tenant_id,
            "message_id": envelope.message_id,
        }
        retry_not_before = float(envelope.payload.get("_retry_not_before", 0.0) or 0.0)
        if retry_not_before > time.time():
            await redis.xadd(RAW_STREAM, encode_message(envelope), maxlen=50000)
            await redis.xack(RAW_STREAM, GROUP, redis_msg_id)
            continue

        try:
            was_new, duplicate = await process_and_save_job(envelope, typesense_client=typesense_client)
            if duplicate:
                await redis.xack(RAW_STREAM, GROUP, redis_msg_id)
                logger.info("consumer_duplicate_skipped", extra={"extra": trace})
                continue
            inserted += 1 if was_new else 0
            await redis.xack(RAW_STREAM, GROUP, redis_msg_id)
            logger.info("consumer_processed", extra={"extra": {**trace, "inserted": int(was_new)}})
        except Exception as exc:
            errors += 1
            next_attempt = envelope.attempt + 1
            if next_attempt <= MAX_ATTEMPTS:
                retry_delay = _retry_backoff_seconds(next_attempt)
                retry_payload = dict(envelope.payload)
                retry_payload["_retry_not_before"] = time.time() + retry_delay
                retry_envelope = build_envelope(
                    tenant_id=envelope.tenant_id,
                    type=envelope.type,
                    source=envelope.source,
                    payload=retry_payload,
                    idempotency_key=envelope.idempotency_key,
                    attempt=next_attempt,
                )
                await redis.xadd(RAW_STREAM, encode_message(retry_envelope), maxlen=50000)
                stream_retries_total.labels(stream=RAW_STREAM, type=envelope.type).inc()
            else:
                await _send_to_dlq(envelope, str(exc), redis_msg_id)
            await redis.xack(RAW_STREAM, GROUP, redis_msg_id)
            logger.error(
                "envelope_processing_failed source=%s job_id=%s attempt=%s error_type=%s error=%s trace_id=%s tenant_id=%s",
                envelope.source,
                str(envelope.payload.get("source_id") or envelope.payload.get("id") or ""),
                envelope.attempt,
                type(exc).__name__,
                str(exc),
                envelope.idempotency_key,
                envelope.tenant_id,
            )

    await _update_stream_health_metrics()
    return {"processed": processed, "inserted": inserted, "errors": errors}


async def run_ingestion_consumer(worker_id: str) -> None:
    """Run a Redis Streams consumer loop using consumer groups."""

    while True:
        await process_stream_batch(worker_id=worker_id, count=10, block_ms=5000)
