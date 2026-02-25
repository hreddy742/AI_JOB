"""Job search and saved-job routes."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from functools import lru_cache
import logging
import re
from typing import Any
from uuid import UUID

import chromadb
import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import apply_tenant_rls, get_current_token, get_db
from core.security import TokenPayload
from db.models.job import Job
from db.models.resume import Resume
from db.session import AsyncSessionFactory
from schemas.job import JobResponse, JobSearchResponse
from services.ingestion_service import build_user_role_queries, run_default_ingestion_cycle, run_personalized_ingestion_cycle
from services.embedding_service import find_matching_jobs
from services.search_service import get_typesense_client, search_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

def _clean_country_text(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", value.lower()).strip()


@lru_cache(maxsize=1)
def _country_alias_index() -> tuple[dict[str, str], dict[str, set[str]]]:
    alias_to_canonical: dict[str, str] = {}
    canonical_to_aliases: dict[str, set[str]] = {}
    try:
        import pycountry
    except Exception:
        pycountry = None

    if pycountry is not None:
        for country in pycountry.countries:
            canonical = _clean_country_text(getattr(country, "name", ""))
            if not canonical:
                continue
            aliases = {
                canonical,
                _clean_country_text(getattr(country, "official_name", "") or ""),
                _clean_country_text(getattr(country, "common_name", "") or ""),
                _clean_country_text(getattr(country, "alpha_2", "") or ""),
                _clean_country_text(getattr(country, "alpha_3", "") or ""),
            }
            aliases = {a for a in aliases if a}
            canonical_to_aliases[canonical] = aliases
            for alias in aliases:
                alias_to_canonical[alias] = canonical

    # Extra common aliases not always covered by ISO metadata.
    manual_aliases = {
        "america": "united states",
        "u s": "united states",
        "u s a": "united states",
        "uk": "united kingdom",
        "u k": "united kingdom",
    }
    for alias, canonical in manual_aliases.items():
        alias_to_canonical[_clean_country_text(alias)] = _clean_country_text(canonical)
        canonical_to_aliases.setdefault(_clean_country_text(canonical), set()).add(_clean_country_text(alias))

    return alias_to_canonical, canonical_to_aliases


def _canonical_country(value: str | None) -> str:
    raw = _clean_country_text(value or "")
    if not raw:
        return ""
    alias_to_canonical, _ = _country_alias_index()
    return alias_to_canonical.get(raw, raw)


def _country_matches(value: str | None, location_country: str | None, location_city: str | None) -> bool:
    selected = _canonical_country(value)
    if not selected:
        return True
    alias_to_canonical, canonical_to_aliases = _country_alias_index()
    aliases = canonical_to_aliases.get(selected, {selected})

    for haystack in (_clean_country_text(location_country or ""), _clean_country_text(location_city or "")):
        if not haystack:
            continue
        if _canonical_country(haystack) == selected or haystack in aliases:
            return True
        tokens = set(haystack.split())
        for token in tokens:
            mapped = alias_to_canonical.get(token)
            if mapped == selected:
                return True
        for alias in aliases:
            if alias and re.search(rf"(^| )({re.escape(alias)})( |$)", haystack):
                return True
    return False


def _redis_client() -> redis.Redis:
    """Return async Redis client for jobs endpoints."""

    return redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def _trigger_background_backfill_if_needed(
    tenant_id: UUID,
    user_id: UUID,
    resume_id: UUID | None,
    query: str,
    location_country: str | None,
    use_resume_context: bool,
    include_without_resume_context: bool = False,
) -> bool:
    """Trigger one async backfill run with cooldown to keep results fresh."""

    redis_client = _redis_client()
    fingerprint_input = f"{query.strip().lower()}|{(location_country or '').strip().lower()}|{resume_id or ''}"
    fingerprint = hashlib.md5(fingerprint_input.encode("utf-8")).hexdigest()
    cooldown_key = f"jobs:backfill:tenant:{tenant_id}:user:{user_id}:q:{fingerprint}"
    accepted = await redis_client.set(cooldown_key, "1", ex=600, nx=True)
    if not accepted:
        return False

    async def _run() -> None:
        try:
            async with AsyncSessionFactory() as bg_db:
                # Keep the global feed fresh by running the full source cycle.
                await run_default_ingestion_cycle(bg_db, tenant_id)

                async def _run_personalized_with_resume() -> bool:
                    role_queries = await build_user_role_queries(
                        bg_db,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        resume_id=resume_id,
                        explicit_query=query,
                        limit=10,
                    )
                    if not role_queries:
                        return False
                    await run_personalized_ingestion_cycle(
                        bg_db,
                        tenant_id=tenant_id,
                        role_queries=role_queries,
                        location_country=location_country or "United States",
                    )
                    return True

                async def _run_personalized_without_resume() -> bool:
                    role_queries = [query.strip()] if query.strip() else []
                    if not role_queries:
                        return False
                    await run_personalized_ingestion_cycle(
                        bg_db,
                        tenant_id=tenant_id,
                        role_queries=role_queries,
                        location_country=location_country or "United States",
                    )
                    return True

                ran_any = False
                if use_resume_context:
                    ran_any = await _run_personalized_with_resume() or ran_any
                if include_without_resume_context:
                    ran_any = await _run_personalized_without_resume() or ran_any
                if not use_resume_context and not include_without_resume_context:
                    ran_any = await _run_personalized_without_resume() or ran_any

                if not ran_any:
                    return
        except Exception:
            # Keep search endpoint fast and resilient even if backfill fails.
            return

    asyncio.create_task(_run())
    return True


@router.get("/search", response_model=JobSearchResponse)
async def jobs_search(
    q: str = "",
    resume_id: UUID | None = None,
    use_resume_context: bool = True,
    include_without_resume_context: bool = False,
    remote: bool | None = None,
    job_type: str | None = None,
    source: str | None = None,
    experience_level: str | None = None,
    location_city: str | None = None,
    location_state: str | None = None,
    location_country: str | None = None,
    salary_min: float | None = None,
    sponsorship_min: float | None = None,
    days_ago: int | None = None,
    min_hours_ago: int | None = None,
    sort_by: str = Query(default="latest", pattern="^(latest|oldest)$"),
    title_match_mode: str = Query(default="fuzzy", pattern="^(fuzzy|phrase|exact)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> JobSearchResponse:
    """Search jobs using Typesense with faceted filters."""

    filters: dict[str, Any] = {
        "remote": remote,
        "job_type": job_type,
        "source": source,
        "experience_level": experience_level,
        "location_city": location_city,
        "location_state": location_state,
        # Country matching is post-filtered with synonym support.
        "location_country": None,
        "salary_min": salary_min,
        "sponsorship_min": sponsorship_min,
        "days_ago": days_ago,
        "min_hours_ago": min_hours_ago,
    }
    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await search_jobs(
        query=q,
        tenant_id=token.tenant_id,
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        title_match_mode=title_match_mode,
        client=get_typesense_client(),
    )
    ids: list[UUID] = []
    for item in result["items"]:
        try:
            ids.append(UUID(str(item["id"])))
        except (ValueError, KeyError, TypeError):
            continue
    if ids:
        rows = await db.execute(
            select(Job.id, Job.url, Job.location_city, Job.location_state, Job.location_country, Job.posted_at).where(
                Job.tenant_id == tenant_id, Job.id.in_(ids)
            )
        )
        meta_map = {
            str(row[0]): {
                "url": row[1],
                "location_city": row[2] or "",
                "location_state": row[3] or "",
                "location_country": row[4] or "",
                "posted_at": row[5],
            }
            for row in rows.fetchall()
        }
        filtered_items: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for item in result["items"]:
            meta = meta_map.get(str(item.get("id")))
            if not meta:
                continue
            item["url"] = meta["url"]

            if location_state and meta["location_state"].lower() != location_state.strip().lower():
                continue
            if location_city and location_city.strip().lower() not in meta["location_city"].lower():
                continue
            if not _country_matches(location_country, meta["location_country"], meta["location_city"]):
                continue

            posted_at = meta["posted_at"]
            if posted_at is not None:
                if days_ago is not None and posted_at < (now - timedelta(days=int(days_ago))):
                    continue
                if min_hours_ago is not None and posted_at < (now - timedelta(hours=int(min_hours_ago))):
                    continue

            filtered_items.append(item)

        result["items"] = filtered_items
        result["total"] = len(filtered_items)

    refresh_started = False
    try:
        refresh_started = await _trigger_background_backfill_if_needed(
            tenant_id=tenant_id,
            user_id=UUID(token.sub),
            resume_id=resume_id,
            query=q,
            location_country=location_country,
            use_resume_context=use_resume_context,
            include_without_resume_context=include_without_resume_context,
        )
    except Exception as exc:
        logger.warning("jobs_backfill_trigger_failed", extra={"extra": {"tenant_id": str(tenant_id), "error": str(exc)}})

    return JobSearchResponse(**result, refresh_started=refresh_started)


@router.get("/matches")
async def jobs_matches(
    resume_id: UUID,
    n_results: int = Query(default=50, ge=1, le=200),
    min_score: float = Query(default=0.6, ge=0.0, le=1.0),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return semantically matched jobs for a resume."""

    tenant_id = UUID(token.tenant_id)
    user_id = UUID(token.sub)
    await apply_tenant_rls(db, tenant_id)

    resume_result = await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if not resume.embedding_id:
        return {"items": []}

    chroma = chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT)
    items = await find_matching_jobs(resume.embedding_id, chroma, n_results=n_results, min_score=min_score)
    return {"items": items}


@router.get("/saved", response_model=list[JobResponse])
async def list_saved_jobs(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    """List saved jobs for the current user."""

    tenant_id = UUID(token.tenant_id)
    user_id = token.sub
    await apply_tenant_rls(db, tenant_id)

    redis_client = _redis_client()
    key = f"jobs:saved:{user_id}"
    raw_ids = await redis_client.smembers(key)
    if not raw_ids:
        return []

    uuids: list[UUID] = []
    for raw in raw_ids:
        try:
            uuids.append(UUID(raw))
        except ValueError:
            continue

    if not uuids:
        return []

    result = await db.execute(select(Job).where(Job.id.in_(uuids), Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    jobs = result.scalars().all()
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{id}", response_model=JobResponse)
async def get_job(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Get one job detail from PostgreSQL."""

    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(Job).where(Job.id == id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/{id}/save", status_code=status.HTTP_200_OK)
async def save_job(id: UUID, token: TokenPayload = Depends(get_current_token), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Save job to user saved set."""

    tenant_id = UUID(token.tenant_id)
    await apply_tenant_rls(db, tenant_id)

    result = await db.execute(select(Job.id).where(Job.id == id, Job.tenant_id == tenant_id, Job.is_active.is_(True)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    redis_client = _redis_client()
    await redis_client.sadd(f"jobs:saved:{token.sub}", str(id))
    await redis_client.expire(f"jobs:saved:{token.sub}", 60)
    return {"status": "saved"}


@router.delete("/{id}/save", status_code=status.HTTP_200_OK)
async def unsave_job(id: UUID, token: TokenPayload = Depends(get_current_token)) -> dict[str, str]:
    """Remove job from user saved set."""

    redis_client = _redis_client()
    await redis_client.srem(f"jobs:saved:{token.sub}", str(id))
    await redis_client.expire(f"jobs:saved:{token.sub}", 60)
    return {"status": "unsaved"}
