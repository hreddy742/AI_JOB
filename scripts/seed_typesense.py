"""Initialize Typesense jobs collection and seed sample documents."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/apex_apply")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "dev-secret")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("TYPESENSE_HOST", "localhost")
os.environ.setdefault("TYPESENSE_PORT", "8108")
os.environ.setdefault("TYPESENSE_API_KEY", "apex-apply-local-key")

from services.search_service import ensure_jobs_collection, get_typesense_client, index_job


async def main() -> None:
    """Ensure jobs schema exists and insert representative docs."""

    client = get_typesense_client()
    await ensure_jobs_collection(client)

    now = datetime.now(UTC)
    docs = [
        {
            "id": "seed-job-1",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "title": "Senior Backend Engineer",
            "company": "Acme Cloud",
            "description": "Build Python and FastAPI services with PostgreSQL.",
            "location_city": "New York",
            "location_country": "US",
            "remote": True,
            "job_type": "full_time",
            "experience_level": "senior",
            "tags": ["python", "fastapi", "postgres"],
            "salary_min": 140000,
            "salary_max": 190000,
            "sponsorship_score": 0.7,
            "posted_at": now,
            "source": "seed",
            "is_active": True,
        },
        {
            "id": "seed-job-2",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "title": "ML Engineer",
            "company": "Neural Forge",
            "description": "Work on embeddings and model serving infrastructure.",
            "location_city": "San Francisco",
            "location_country": "US",
            "remote": False,
            "job_type": "full_time",
            "experience_level": "mid",
            "tags": ["python", "ml", "pytorch"],
            "salary_min": 160000,
            "salary_max": 220000,
            "sponsorship_score": 0.5,
            "posted_at": now,
            "source": "seed",
            "is_active": True,
        },
    ]

    for doc in docs:
        await index_job(doc, client)


if __name__ == "__main__":
    asyncio.run(main())
