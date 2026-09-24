"""Helpers for exposing Prometheus metrics from ARQ workers."""

from __future__ import annotations

import logging
from threading import Lock

from prometheus_client import start_http_server

logger = logging.getLogger(__name__)

_started_ports: set[int] = set()
_lock = Lock()


def start_worker_metrics_server(port: int | None) -> int | None:
    """Start a Prometheus metrics HTTP server once per process/port."""

    if port is None:
        return None
    normalized = int(port)
    if normalized <= 0:
        return None
    with _lock:
        if normalized in _started_ports:
            return normalized
        start_http_server(normalized, addr="0.0.0.0")
        _started_ports.add(normalized)
    logger.info("worker_metrics_server_started", extra={"extra": {"port": normalized}})
    return normalized
