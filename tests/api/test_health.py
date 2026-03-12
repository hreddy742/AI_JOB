"""Tests for health check router."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.health import router


@pytest.fixture()
def app():
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_health_returns_200_when_all_healthy(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.return_value = [{"name": "jobs"}]

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(return_value=True)),
        patch("routers.health._probe_ollama", AsyncMock(return_value=True)),
        patch("routers.health._probe_smtp", AsyncMock(return_value=True)),
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
    assert body["typesense"] == "ok"
    assert body["minio"] == "ok"
    assert body["ollama"] == "ok"
    assert body["smtp"] == "ok"
    assert "queue_depths" in body


def test_health_returns_degraded_on_postgres_failure(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(side_effect=ConnectionError("db down"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.return_value = [{"name": "jobs"}]

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(return_value=True)),
        patch("routers.health._probe_ollama", AsyncMock(return_value=True)),
        patch("routers.health._probe_smtp", AsyncMock(return_value=True)),
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "error" in body["postgres"]


def test_health_returns_degraded_on_redis_failure(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.return_value = [{"name": "jobs"}]

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(return_value=True)),
        patch("routers.health._probe_ollama", AsyncMock(return_value=True)),
        patch("routers.health._probe_smtp", AsyncMock(return_value=True)),
    ):
        resp = client.get("/health")

    body = resp.json()
    assert body["status"] == "degraded"
    assert "error" in body["redis"]


def test_health_returns_degraded_on_typesense_failure(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.side_effect = Exception("typesense down")

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(return_value=True)),
        patch("routers.health._probe_ollama", AsyncMock(return_value=True)),
        patch("routers.health._probe_smtp", AsyncMock(return_value=True)),
    ):
        resp = client.get("/health")

    body = resp.json()
    assert body["status"] == "degraded"
    assert "error" in body["typesense"]


def test_health_response_contains_timestamp_and_environment(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.return_value = [{"name": "jobs"}]

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(return_value=True)),
        patch("routers.health._probe_ollama", AsyncMock(return_value=True)),
        patch("routers.health._probe_smtp", AsyncMock(return_value=True)),
    ):
        resp = client.get("/health")

    body = resp.json()
    assert "timestamp" in body
    assert "environment" in body


def test_health_returns_degraded_when_optional_dependencies_fail(client):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=0)

    mock_typesense = MagicMock()
    mock_typesense.collections.retrieve.return_value = [{"name": "jobs"}]

    with (
        patch("routers.health.AsyncSessionFactory", return_value=mock_session),
        patch("routers.health.get_redis", return_value=mock_redis),
        patch("routers.health.get_typesense_client", return_value=mock_typesense),
        patch("routers.health._probe_minio", AsyncMock(side_effect=ConnectionError("minio down"))),
        patch("routers.health._probe_ollama", AsyncMock(side_effect=ConnectionError("ollama down"))),
        patch("routers.health._probe_smtp", AsyncMock(side_effect=ConnectionError("smtp down"))),
    ):
        resp = client.get("/health")

    body = resp.json()
    assert body["status"] == "degraded"
    assert "error" in body["minio"]
    assert "error" in body["ollama"]
    assert "error" in body["smtp"]
