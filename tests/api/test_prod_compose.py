from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_prod_compose_includes_required_workers():
    compose = _load_compose(ROOT / "docker-compose.prod.yml")
    services = compose.get("services", {})

    required = {
        "resume-worker",
        "tailoring-worker",
        "embedding-worker",
        "job-requirements-worker",
        "job-coverage-worker",
        "job-detail-enrichment-worker",
        "automation-worker",
        "campaign-worker",
        "referral-worker",
        "notification-worker",
    }

    missing = required.difference(services)
    assert not missing, f"Missing required production workers: {sorted(missing)}"


def test_local_compose_uses_pgbouncer_for_app_database_urls():
    compose = _load_compose(ROOT / "infra" / "docker-compose.yml")
    services = compose.get("services", {})
    app_services = {
        "api",
        "resume-worker",
        "tailoring-worker",
        "embedding-worker",
        "job-requirements-worker",
        "job-coverage-worker",
        "job-detail-enrichment-worker",
        "automation-worker",
        "campaign-worker",
        "referral-worker",
        "notification-worker",
    }

    for service_name in app_services:
        env = (services.get(service_name) or {}).get("environment", {})
        assert env.get("DATABASE_URL") == "postgresql+asyncpg://postgres:postgres@pgbouncer:5432/apex_apply"
