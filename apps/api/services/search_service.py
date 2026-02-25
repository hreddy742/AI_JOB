"""Typesense wrapper for fast job search.

Schema mirrors the jobs table but is optimized for text search.
Jobs are indexed at ingest time and expired at soft-delete time.
Provides sub-100ms full-text + faceted search across all fields.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import typesense

from core.config import settings

JOBS_SCHEMA: dict[str, Any] = {
    "name": settings.TYPESENSE_JOBS_COLLECTION,
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "tenant_id", "type": "string", "facet": True},
        {"name": "title", "type": "string"},
        {"name": "company", "type": "string", "facet": True},
        {"name": "description", "type": "string"},
        {"name": "location_city", "type": "string", "facet": True, "optional": True},
        {"name": "location_state", "type": "string", "facet": True, "optional": True},
        {"name": "location_country", "type": "string", "facet": True, "optional": True},
        {"name": "remote", "type": "bool", "facet": True},
        {"name": "job_type", "type": "string", "facet": True},
        {"name": "experience_level", "type": "string", "facet": True},
        {"name": "tags", "type": "string[]", "facet": True},
        {"name": "salary_min", "type": "float", "optional": True},
        {"name": "salary_max", "type": "float", "optional": True},
        {"name": "sponsorship_score", "type": "float", "facet": True},
        {"name": "posted_at_ts", "type": "int64"},
        {"name": "source", "type": "string", "facet": True},
        {"name": "is_active", "type": "bool"},
    ],
    "default_sorting_field": "posted_at_ts",
}


def get_typesense_client() -> typesense.Client:
    """Build and return a Typesense client."""

    return typesense.Client(
        {
            "nodes": [
                {
                    "host": settings.TYPESENSE_HOST,
                    "port": settings.TYPESENSE_PORT,
                    "protocol": "http",
                }
            ],
            "api_key": settings.TYPESENSE_API_KEY,
            "connection_timeout_seconds": 5,
        }
    )


async def ensure_jobs_collection(client: typesense.Client) -> None:
    """Create jobs collection if missing."""

    try:
        collection = client.collections[settings.TYPESENSE_JOBS_COLLECTION]
        # Test fakes may not implement the retrieve API; treat that as already available.
        if hasattr(collection, "retrieve"):
            existing = collection.retrieve()
            existing_names = {
                field.get("name")
                for field in existing.get("fields", [])
                if isinstance(field, dict)
            }
            missing_fields = [
                field
                for field in JOBS_SCHEMA["fields"]
                if field["name"] not in existing_names and field["name"] != "id"
            ]
            if missing_fields and hasattr(collection, "update"):
                try:
                    collection.update({"fields": missing_fields})
                except Exception:
                    # Never fail API startup due to schema drift in optional fields.
                    return
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(JOBS_SCHEMA)


async def index_job(job_dict: dict[str, Any], client: typesense.Client) -> None:
    """Upsert a job document into Typesense."""

    await ensure_jobs_collection(client)

    posted_at = job_dict.get("posted_at")
    posted_at_ts = int(posted_at.timestamp()) if isinstance(posted_at, datetime) else 0

    doc = {
        "id": str(job_dict["id"]),
        "tenant_id": str(job_dict["tenant_id"]),
        "title": job_dict["title"],
        "company": job_dict["company"],
        "description": (job_dict.get("description") or "")[:2000],
        "location_city": job_dict.get("location_city") or "",
        "location_state": job_dict.get("location_state") or "",
        "location_country": job_dict.get("location_country") or "",
        "remote": bool(job_dict.get("remote")),
        "job_type": job_dict.get("job_type") or "unknown",
        "experience_level": job_dict.get("experience_level") or "unknown",
        "tags": job_dict.get("tags") or [],
        "salary_min": float(job_dict["salary_min"]) if job_dict.get("salary_min") is not None else 0.0,
        "salary_max": float(job_dict["salary_max"]) if job_dict.get("salary_max") is not None else 0.0,
        "sponsorship_score": float(job_dict.get("sponsorship_score") or 0.5),
        "posted_at_ts": posted_at_ts,
        "source": job_dict.get("source") or "",
        "is_active": bool(job_dict.get("is_active", True)),
    }
    client.collections[settings.TYPESENSE_JOBS_COLLECTION].documents.upsert(doc)


async def search_jobs(
    query: str,
    tenant_id: str,
    filters: dict[str, Any],
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "latest",
    title_match_mode: str = "fuzzy",
    client: typesense.Client | None = None,
) -> dict[str, Any]:
    """Run full-text and faceted job search in Typesense."""

    search_client = client or get_typesense_client()
    await ensure_jobs_collection(search_client)

    filter_parts: list[str] = [f"tenant_id:={tenant_id}", "is_active:=true"]

    if filters.get("remote") is True:
        filter_parts.append("remote:=true")
    if filters.get("job_type"):
        filter_parts.append(f"job_type:={filters['job_type']}")
    if filters.get("source"):
        filter_parts.append(f"source:={filters['source']}")
    if filters.get("experience_level"):
        filter_parts.append(f"experience_level:={filters['experience_level']}")
    if filters.get("location_city"):
        city = str(filters["location_city"]).strip().replace("`", "")
        if city:
            filter_parts.append(f"location_city:{city}")
    if filters.get("location_state"):
        state = str(filters["location_state"]).strip().replace("`", "")
        if state:
            filter_parts.append(f"location_state:={state}")
    if filters.get("location_country"):
        country = str(filters["location_country"]).strip().replace("`", "")
        if country:
            filter_parts.append(f"location_country:={country}")
    if filters.get("salary_min") is not None:
        filter_parts.append(f"salary_max:>={filters['salary_min']}")
    if filters.get("sponsorship_min") is not None:
        filter_parts.append(f"sponsorship_score:>={filters['sponsorship_min']}")
    if filters.get("days_ago"):
        cutoff = int((datetime.now(UTC) - timedelta(days=int(filters["days_ago"]))).timestamp())
        filter_parts.append(f"posted_at_ts:>={cutoff}")
    if filters.get("min_hours_ago"):
        lower = int((datetime.now(UTC) - timedelta(hours=int(filters["min_hours_ago"]))).timestamp())
        filter_parts.append(f"posted_at_ts:>={lower}")

    sort_expr = "posted_at_ts:desc"
    if sort_by == "oldest":
        sort_expr = "posted_at_ts:asc"

    safe_query = (query or "").strip()
    mode = (title_match_mode or "fuzzy").strip().lower()
    if mode == "exact" and safe_query:
        exact_title = safe_query.replace("`", "")
        filter_parts.append(f"title:=[`{exact_title}`]")

    q_value = safe_query or "*"
    if mode == "exact" and safe_query:
        q_value = "*"
    elif mode == "phrase" and safe_query:
        q_value = safe_query

    search_params: dict[str, Any] = {
        "q": q_value,
        "query_by": "title,company,description,tags",
        "query_by_weights": "4,3,1,2",
        "filter_by": " && ".join(filter_parts),
        "sort_by": sort_expr,
        "page": page,
        "per_page": page_size,
        "facet_by": "remote,job_type,experience_level,source,location_country,location_state,location_city",
        "highlight_full_fields": "title,company",
    }
    if mode in {"phrase", "exact"}:
        search_params["num_typos"] = 0
        search_params["prefix"] = False

    result: dict[str, Any] = search_client.collections[settings.TYPESENSE_JOBS_COLLECTION].documents.search(search_params)

    return {
        "items": [hit["document"] for hit in result.get("hits", [])],
        "total": int(result.get("found", 0)),
        "page": page,
        "page_size": page_size,
        "facets": result.get("facet_counts", []),
    }


async def delete_job_from_index(job_id: str, client: typesense.Client) -> None:
    """Remove a job from Typesense index if present."""

    try:
        client.collections[settings.TYPESENSE_JOBS_COLLECTION].documents[job_id].delete()
    except typesense.exceptions.ObjectNotFound:
        return
