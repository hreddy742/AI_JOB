"""Shared LLM/Ollama telemetry and request helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from core.config import settings
from core.redis import get_redis

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    # Simple provider-agnostic estimate to avoid tokenizer dependencies.
    return max(0, int(round(len(text or "") / 4.0)))


def _messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(str(msg.get("content") or "")) for msg in messages)


async def _record_metrics(
    *,
    flow: str,
    model: str,
    prompt_chars: int,
    output_chars: int,
    latency_ms: float,
    success: bool,
    error_type: str | None = None,
) -> None:
    day = datetime.now(UTC).date().isoformat()
    fields = {
        "calls": 1,
        "success": 1 if success else 0,
        "failed": 0 if success else 1,
        "prompt_chars": int(max(0, prompt_chars)),
        "output_chars": int(max(0, output_chars)),
        "prompt_tokens_est": _estimate_tokens("x" * max(0, prompt_chars)),
        "output_tokens_est": _estimate_tokens("x" * max(0, output_chars)),
        "latency_ms_total": float(max(0.0, latency_ms)),
    }
    keys = [
        f"metrics:llm:day:{day}",
        f"metrics:llm:flow:{flow}:{day}",
        f"metrics:llm:model:{model}:{day}",
    ]
    try:
        redis = get_redis()
        for key in keys:
            for field, amount in fields.items():
                if isinstance(amount, float):
                    await redis.hincrbyfloat(key, field, amount)
                else:
                    await redis.hincrby(key, field, int(amount))
            await redis.hset(
                key,
                mapping={
                    "last_updated": datetime.now(UTC).isoformat(),
                    "last_model": model,
                    "last_flow": flow,
                    "last_error_type": error_type or "",
                },
            )
            await redis.expire(key, 14 * 24 * 3600)
    except Exception:
        logger.warning("llm_metrics_write_failed", extra={"extra": {"flow": flow, "model": model}})

    logger.info(
        "llm_call",
        extra={
            "extra": {
                "flow": flow,
                "model": model,
                "success": success,
                "latency_ms": round(float(latency_ms), 3),
                "prompt_chars": int(prompt_chars),
                "output_chars": int(output_chars),
                "prompt_tokens_est": _estimate_tokens("x" * max(0, prompt_chars)),
                "output_tokens_est": _estimate_tokens("x" * max(0, output_chars)),
                "error_type": error_type,
            }
        },
    )


async def ollama_chat(
    *,
    flow: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_s: float = 120.0,
    stream: bool = False,
    output_format: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Ollama chat endpoint and emit standardized telemetry."""

    started = datetime.now(UTC)
    prompt_chars = _messages_chars(messages)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": bool(stream),
    }
    if output_format:
        payload["format"] = output_format
    if options is not None:
        payload["options"] = options
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        output_chars = len(str((data or {}).get("message", {}).get("content", "") or ""))
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000.0
        await _record_metrics(
            flow=flow,
            model=model,
            prompt_chars=prompt_chars,
            output_chars=output_chars,
            latency_ms=latency_ms,
            success=True,
        )
        return data
    except Exception as exc:
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000.0
        await _record_metrics(
            flow=flow,
            model=model,
            prompt_chars=prompt_chars,
            output_chars=0,
            latency_ms=latency_ms,
            success=False,
            error_type=type(exc).__name__,
        )
        raise


async def llm_generate(
    prompt: str,
    system: str = "",
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 150,
    timeout_s: float = 120.0,
) -> str:
    """Generate plain-text output through Ollama chat with bounded token budgets."""

    capped_tokens = max(1, min(int(max_tokens or 0), 400))
    messages = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = await ollama_chat(
        flow="llm_generate",
        model=model or settings.STRUCTURED_LLM_MODEL,
        messages=messages,
        timeout_s=timeout_s,
        stream=False,
        options={"temperature": float(temperature), "num_predict": capped_tokens},
    )
    return str(payload.get("message", {}).get("content", "") or "").strip()


async def record_streaming_ollama_call(
    *,
    flow: str,
    model: str,
    prompt_chars: int,
    output_chars: int,
    started_at: datetime,
    success: bool,
    error_type: str | None = None,
) -> None:
    """Record telemetry for call sites that stream tokens manually."""

    latency_ms = (datetime.now(UTC) - started_at).total_seconds() * 1000.0
    await _record_metrics(
        flow=flow,
        model=model,
        prompt_chars=prompt_chars,
        output_chars=output_chars,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
    )
