"""Standard Redis Stream message envelope for ingestion pipelines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Envelope:
    """Canonical stream envelope used by producers and consumers."""

    v: str
    message_id: str
    tenant_id: str
    type: str
    source: str
    idempotency_key: str
    attempt: int
    created_at: str
    payload: dict[str, Any]


def build_envelope(
    *,
    tenant_id: str,
    type: str,
    source: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
    attempt: int = 0,
    message_id: str | None = None,
    created_at: str | None = None,
) -> Envelope:
    """Create a new validated envelope."""

    if not tenant_id or not str(tenant_id).strip():
        raise ValueError("tenant_id is required in stream envelope")
    now = created_at or datetime.now(UTC).isoformat()
    msg_id = message_id or str(uuid4())
    idem = idempotency_key or msg_id
    return Envelope(
        v="1",
        message_id=msg_id,
        tenant_id=str(tenant_id),
        type=type,
        source=source,
        idempotency_key=idem,
        attempt=max(int(attempt), 0),
        created_at=now,
        payload=payload,
    )


def encode_message(envelope: Envelope) -> dict[str, str]:
    """Encode envelope to Redis Stream field map."""

    if not envelope.tenant_id or not str(envelope.tenant_id).strip():
        raise ValueError("tenant_id is required in stream envelope")
    return {
        "v": envelope.v,
        "message_id": envelope.message_id,
        "tenant_id": envelope.tenant_id,
        "type": envelope.type,
        "source": envelope.source,
        "idempotency_key": envelope.idempotency_key,
        "attempt": str(int(envelope.attempt)),
        "created_at": envelope.created_at,
        "payload": json.dumps(envelope.payload, default=str),
    }


def decode_message(fields: dict[str, Any]) -> Envelope:
    """Decode and validate stream message fields."""

    required = {
        "v",
        "message_id",
        "tenant_id",
        "type",
        "source",
        "idempotency_key",
        "attempt",
        "created_at",
        "payload",
    }
    missing = [key for key in required if key not in fields]
    if missing:
        raise ValueError(f"invalid envelope: missing fields: {', '.join(sorted(missing))}")
    tenant_id = str(fields.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("invalid envelope: tenant_id is required")
    raw_payload = fields.get("payload")
    payload = raw_payload if isinstance(raw_payload, dict) else json.loads(str(raw_payload))
    if not isinstance(payload, dict):
        raise ValueError("invalid envelope: payload must be a JSON object")
    return Envelope(
        v=str(fields["v"]),
        message_id=str(fields["message_id"]),
        tenant_id=tenant_id,
        type=str(fields["type"]),
        source=str(fields["source"]),
        idempotency_key=str(fields["idempotency_key"]),
        attempt=int(fields["attempt"]),
        created_at=str(fields["created_at"]),
        payload=payload,
    )
