from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.search_service import index_job, search_jobs


class FakeDocs:
    def __init__(self):
        self._docs = {}

    def upsert(self, doc):
        self._docs[doc["id"]] = doc

    def search(self, params):
        items = list(self._docs.values())
        if "remote:=true" in params.get("filter_by", ""):
            items = [d for d in items if d.get("remote")]
        return {
            "hits": [{"document": d} for d in items],
            "found": len(items),
            "facet_counts": [{"field_name": "job_type"}],
        }


class FakeCollection:
    def __init__(self):
        self.documents = FakeDocs()


class FakeCollections:
    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, _):
        return self.collection


class FakeClient:
    def __init__(self):
        self.collections = FakeCollections()


@pytest.mark.asyncio
async def test_job_indexed_after_ingest() -> None:
    client = FakeClient()
    await index_job(
        {
            "id": "1",
            "tenant_id": "t1",
            "title": "Python Engineer",
            "company": "Acme",
            "description": "Backend role",
            "location_city": "NYC",
            "location_country": "US",
            "remote": True,
            "job_type": "full_time",
            "experience_level": "mid",
            "tags": ["python"],
            "salary_min": 100000,
            "salary_max": 150000,
            "sponsorship_score": 0.7,
            "posted_at": datetime.now(UTC),
            "source": "remoteok",
            "is_active": True,
        },
        client,
    )
    result = await search_jobs("Python", "t1", {}, client=client)
    assert any(item["title"] == "Python Engineer" for item in result["items"])


@pytest.mark.asyncio
async def test_search_filters_remote() -> None:
    client = FakeClient()
    await index_job(
        {
            "id": "r",
            "tenant_id": "t1",
            "title": "Remote Job",
            "company": "A",
            "description": "d",
            "location_city": "",
            "location_country": "US",
            "remote": True,
            "job_type": "full_time",
            "experience_level": "mid",
            "tags": [],
            "salary_min": 0,
            "salary_max": 0,
            "sponsorship_score": 0.5,
            "posted_at": datetime.now(UTC),
            "source": "x",
            "is_active": True,
        },
        client,
    )
    await index_job(
        {
            "id": "o",
            "tenant_id": "t1",
            "title": "Onsite Job",
            "company": "B",
            "description": "d",
            "location_city": "",
            "location_country": "US",
            "remote": False,
            "job_type": "full_time",
            "experience_level": "mid",
            "tags": [],
            "salary_min": 0,
            "salary_max": 0,
            "sponsorship_score": 0.5,
            "posted_at": datetime.now(UTC),
            "source": "x",
            "is_active": True,
        },
        client,
    )

    result = await search_jobs("*", "t1", {"remote": True}, client=client)
    assert all(item["remote"] is True for item in result["items"])


@pytest.mark.asyncio
async def test_search_returns_correct_facets() -> None:
    client = FakeClient()
    await index_job(
        {
            "id": "1",
            "tenant_id": "t1",
            "title": "A",
            "company": "A",
            "description": "d",
            "location_city": "",
            "location_country": "US",
            "remote": True,
            "job_type": "contract",
            "experience_level": "mid",
            "tags": [],
            "salary_min": 0,
            "salary_max": 0,
            "sponsorship_score": 0.5,
            "posted_at": datetime.now(UTC),
            "source": "x",
            "is_active": True,
        },
        client,
    )
    result = await search_jobs("*", "t1", {}, client=client)
    assert any(f.get("field_name") == "job_type" for f in result["facets"])
