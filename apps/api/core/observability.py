"""Shared observability counters and gauges."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


stream_retries_total = Counter(
    "apex_stream_retries_total",
    "Total stream message retries.",
    ["stream", "type"],
)

stream_dlq_total = Counter(
    "apex_stream_dlq_total",
    "Total stream messages sent to DLQ.",
    ["stream", "type"],
)

stream_pending_age_seconds = Gauge(
    "apex_stream_pending_oldest_age_seconds",
    "Oldest pending message age (seconds) by stream/group.",
    ["stream", "group"],
)

stream_queue_lag = Gauge(
    "apex_stream_queue_lag",
    "Approximate queue lag (stream length).",
    ["stream"],
)

rerank_outcomes_total = Counter(
    "apex_rerank_outcomes_total",
    "Total rerank outcomes by type.",
    ["outcome"],
)

rerank_latency_ms = Histogram(
    "apex_rerank_latency_ms",
    "Rerank execution latency in milliseconds.",
    buckets=(25, 50, 100, 200, 400, 800, 1200, 2000, 4000),
)

browser_agent_runs_total = Counter(
    "apex_browser_agent_runs_total",
    "Total Browser Agent V1 runs by launch mode and status.",
    ["mode", "status"],
)

browser_agent_pauses_total = Counter(
    "apex_browser_agent_pauses_total",
    "Total Browser Agent V1 pauses by reason.",
    ["reason_code"],
)

browser_agent_duration_seconds = Histogram(
    "apex_browser_agent_duration_seconds",
    "Browser Agent V1 run duration in seconds.",
    buckets=(5, 15, 30, 60, 120, 300, 600, 900, 1800, 3600),
)
