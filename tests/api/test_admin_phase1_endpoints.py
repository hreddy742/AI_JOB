from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

import routers.admin as admin_router
from core.security import TokenPayload
import services.feature_flags as feature_flags


class _ExecResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class _FakeRedis:
    def __init__(self, payloads: dict[str, dict[str, str]], kv: dict[str, str] | None = None):
        self._payloads = payloads
        self._kv = kv or {}

    async def hgetall(self, key: str) -> dict[str, str]:
        return self._payloads.get(key, {})

    async def get(self, key: str):
        return self._kv.get(key)

    async def set(self, key: str, value: str):
        self._kv[key] = value
        return True

    async def delete(self, key: str):
        self._kv.pop(key, None)
        return 1

    async def xlen(self, key: str):
        value = self._kv.get(f"xlen:{key}")
        return int(value or 0)

    async def xpending(self, stream: str, group: str):
        key = f"xpending:{stream}:{group}"
        return self._kv.get(key, {"pending": 0})


def _admin_token() -> TokenPayload:
    return TokenPayload(sub=str(uuid4()), role="admin", tid=str(uuid4()), exp=9999999999, iat=1, type="access")


def test_coverage_dashboard_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()

    now = datetime.now(UTC)
    today = now.date().isoformat()

    class _DB:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return _ExecResult(rows=[("greenhouse", 12), ("lever", 5)])
            if self.calls == 2:
                return _ExecResult(rows=[("greenhouse", 3)])
            if self.calls == 3:
                return _ExecResult(scalar=4)
            if self.calls == 4:
                return _ExecResult(scalar=6)
            if self.calls == 5:
                return _ExecResult(
                    rows=[
                        (
                            now - timedelta(minutes=25),
                            {"source": "greenhouse", "new_jobs": 3, "errors": 1},
                        )
                    ]
                )
            raise AssertionError("Unexpected query count")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token

    monkeypatch.setattr(admin_router, "apply_tenant_rls", AsyncMock())
    monkeypatch.setattr(admin_router, "adapter_factories", lambda: {"greenhouse": object(), "lever": object()})
    monkeypatch.setattr(
        admin_router,
        "get_redis",
        lambda: _FakeRedis(
            {
                f"metrics:coverage:greenhouse:{today}": {
                    "jobs_ingested_per_source": "10",
                    "jobs_failed_per_source": "2",
                    "freshness_latency_seconds": "120.5",
                },
                f"metrics:ingestion:greenhouse:{today}": {
                    "inserted": "8",
                    "updated": "1",
                    "skipped": "0",
                    "errors": "1",
                },
            }
        ),
    )

    client = TestClient(app)
    response = client.get("/admin/coverage/dashboard?days=1&stale_after_minutes=60")
    assert response.status_code == 200
    body = response.json()

    assert body["summary"]["typesense_backlog"] == 4
    assert body["summary"]["requirements_backlog"] == 6
    assert body["summary"]["sources_total"] == 2
    assert len(body["sources"]) == 2
    greenhouse = next(item for item in body["sources"] if item["source"] == "greenhouse")
    assert greenhouse["active_jobs"] == 12
    assert greenhouse["runs_window"] == 1
    assert greenhouse["coverage_metrics"]["jobs_ingested"] == 10
    assert greenhouse["ingestion_metrics"]["inserted"] == 8


def test_requirements_status_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()
    now = datetime.now(UTC)

    class _DB:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return _ExecResult(rows=[("queued", 7), ("processing", 2), ("completed", 11), ("failed", 1)])
            if self.calls == 2:
                return _ExecResult(scalar=1)
            if self.calls == 3:
                return _ExecResult(scalar=now - timedelta(minutes=45))
            raise AssertionError("Unexpected query count")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    monkeypatch.setattr(admin_router, "apply_tenant_rls", AsyncMock())

    client = TestClient(app)
    response = client.get("/admin/requirements/status?stale_minutes=30")
    assert response.status_code == 200
    body = response.json()

    assert body["counts"]["queued"] == 7
    assert body["counts"]["processing"] == 2
    assert body["counts"]["completed"] == 11
    assert body["counts"]["failed"] == 1
    assert body["stale_processing"] == 1
    assert body["oldest_queued_age_minutes"] >= 45


def test_rerank_status_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()
    today = datetime.now(UTC).date().isoformat()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token

    monkeypatch.setattr(
        admin_router,
        "get_redis",
        lambda: _FakeRedis(
            {
                f"metrics:rerank:{token.tenant_id}:{today}": {
                    "attempts": "10",
                    "applied": "7",
                    "timeout": "1",
                    "failed": "1",
                    "skipped_disabled": "0",
                    "skipped_min_candidates": "1",
                    "candidates_total": "120",
                    "latency_ms_total": "2450.5",
                    "last_outcome": "applied",
                    "last_updated": f"{today}T12:00:00+00:00",
                }
            }
        ),
    )

    client = TestClient(app)
    response = client.get("/admin/ranking/rerank-status?days=1")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["attempts"] == 10
    assert body["summary"]["applied"] == 7
    assert body["summary"]["timeout"] == 1
    assert body["summary"]["failed"] == 1
    assert body["summary"]["apply_rate"] == 0.7
    assert body["summary"]["average_latency_ms"] > 300


def test_rerank_readiness_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()
    today = datetime.now(UTC).date().isoformat()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    monkeypatch.setattr(
        admin_router,
        "get_redis",
        lambda: _FakeRedis(
            {
                f"metrics:rerank:{token.tenant_id}:{today}": {
                    "attempts": "120",
                    "applied": "110",
                    "timeout": "4",
                    "failed": "1",
                    "skipped_disabled": "0",
                    "skipped_min_candidates": "5",
                    "candidates_total": "1600",
                    "latency_ms_total": "53200",
                    "last_outcome": "applied",
                    "last_updated": f"{today}T15:00:00+00:00",
                }
            }
        ),
    )

    client = TestClient(app)
    response = client.get(
        "/admin/ranking/rerank-readiness?days=1&min_attempts=100&max_timeout_rate=0.05&max_failure_rate=0.02&max_average_latency_ms=800"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ready_to_enable_reranking"] is True
    assert body["checks"]["min_attempts"] is True
    assert body["checks"]["timeout_rate"] is True
    assert body["checks"]["failure_rate"] is True
    assert body["checks"]["average_latency_ms"] is True


def test_rerank_config_endpoints(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    fake = _FakeRedis(payloads={}, kv={})
    monkeypatch.setattr(feature_flags, "get_redis", lambda: fake)
    feature_flags._cache.clear()
    monkeypatch.setattr(admin_router.settings, "ENABLE_RERANKING", False)

    client = TestClient(app)
    r1 = client.get("/admin/ranking/rerank-config")
    assert r1.status_code == 200
    assert r1.json()["effective_enabled"] is False

    r2 = client.put("/admin/ranking/rerank-config", json={"enabled": True})
    assert r2.status_code == 200
    assert r2.json()["tenant_override"] is True
    assert r2.json()["effective_enabled"] is True

    r3 = client.put("/admin/ranking/rerank-config", json={"enabled": None})
    assert r3.status_code == 200
    assert r3.json()["tenant_override"] is None


def test_alerts_status_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    fake = _FakeRedis(
        payloads={},
        kv={
            "xlen:stream:alerts:ready": "12",
            "xlen:stream:alerts:failed": "3",
            "xpending:stream:alerts:ready:alerts-delivery": {"pending": 4},
        },
    )
    monkeypatch.setattr(admin_router, "get_redis", lambda: fake)

    client = TestClient(app)
    resp = client.get("/admin/alerts/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["ready"] == 12
    assert body["counts"]["pending"] == 4
    assert body["counts"]["failed_dlq"] == 3


def test_llm_usage_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()
    today = datetime.now(UTC).date().isoformat()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    fake = _FakeRedis(
        payloads={
            f"metrics:llm:day:{today}": {
                "calls": "10",
                "success": "9",
                "failed": "1",
                "prompt_chars": "4000",
                "output_chars": "1800",
                "prompt_tokens_est": "1000",
                "output_tokens_est": "450",
                "latency_ms_total": "2250",
                "last_updated": f"{today}T12:00:00+00:00",
            },
            f"metrics:llm:flow:screening_answer_draft:{today}": {
                "calls": "3",
                "success": "3",
                "failed": "0",
                "prompt_tokens_est": "250",
                "output_tokens_est": "120",
                "latency_ms_total": "420",
            },
        },
        kv={},
    )
    monkeypatch.setattr(admin_router, "get_redis", lambda: fake)

    client = TestClient(app)
    resp = client.get("/admin/llm/usage?days=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["calls"] == 10
    assert body["summary"]["success_rate"] == 0.9
    assert body["flows"]["screening_answer_draft"]["calls"] == 3


def test_ingestion_trigger_is_tenant_scoped(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router.router)
    token = _admin_token()

    class _DB:
        async def execute(self, _query):
            raise AssertionError("No DB query expected")

    db = _DB()

    async def _get_db():
        yield db

    async def _get_token():
        return token

    app.dependency_overrides[admin_router.get_db] = _get_db
    app.dependency_overrides[admin_router.get_current_token] = _get_token
    monkeypatch.setattr(admin_router, "apply_tenant_rls", AsyncMock())
    monkeypatch.setattr(admin_router, "adapter_factories", lambda: {"greenhouse": object(), "lever": object()})
    scoped_run = AsyncMock(return_value={"greenhouse": 4})
    monkeypatch.setattr(admin_router, "run_ingestion_for_sources", scoped_run)

    client = TestClient(app)
    response = client.post("/admin/ingestion/trigger?source_name=greenhouse")
    assert response.status_code == 200
    body = response.json()

    assert body["source"] == "greenhouse"
    assert body["results"]["greenhouse"] == 4
    assert body["tenant_id"] == token.tenant_id
    scoped_run.assert_awaited_once()
    assert scoped_run.await_args.args[1] == UUID(token.tenant_id)
    assert scoped_run.await_args.args[2] == ["greenhouse"]
    assert scoped_run.await_args.kwargs["min_age_hours"] == 0
