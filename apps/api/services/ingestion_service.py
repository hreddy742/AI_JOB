"""In-process ingestion orchestration used by API startup and admin triggers."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import chromadb
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.adzuna import AdzunaAdapter
from adapters.arbeitnow import ArbeitnowAdapter
from adapters.greenhouse_feed import GreenhouseFeedAdapter
from adapters.jobspy import JobSpyAdapter
from adapters.lever_feed import LeverFeedAdapter
from adapters.remoteok import RemoteOKAdapter
from adapters.the_muse import TheMuseAdapter
from adapters.usajobs import USAJobsAdapter
from core.config import settings
from db.models.job import Job
from db.models.enums import SeverityEnum
from db.models.resume import Resume
from db.models.resume_parsed_data import ResumeParsedData
from db.models.supervisor_log import SupervisorLog
from db.models.user_profile import UserProfile
from services.job_service import upsert_job
from services.search_service import delete_job_from_index, get_typesense_client

logger = logging.getLogger(__name__)

ADAPTERS: dict[str, Any] = {
    "greenhouse": GreenhouseFeedAdapter(),
    "lever": LeverFeedAdapter(),
    "remoteok": RemoteOKAdapter(),
    "adzuna": AdzunaAdapter(api_key=settings.ADZUNA_API_KEY, app_id=settings.ADZUNA_APP_ID),
    "arbeitnow": ArbeitnowAdapter(),
    "the_muse": TheMuseAdapter(api_key=settings.THE_MUSE_API_KEY),
    "usajobs": USAJobsAdapter(api_key=settings.USAJOBS_API_KEY),
    "jobspy": JobSpyAdapter(),
}

DEFAULT_INGESTION_SOURCES: tuple[str, ...] = (
    "remoteok",
    "arbeitnow",
    "greenhouse",
    "lever",
    "adzuna",
    "the_muse",
    "usajobs",
    "jobspy",
)

SEARCH_QUERIES: tuple[str, ...] = (
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "full stack engineer",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "devops engineer",
    "cloud engineer",
    "product manager",
)

PERSONALIZED_INGESTION_SOURCES: tuple[str, ...] = DEFAULT_INGESTION_SOURCES

DEFAULT_JOBSPY_SITE_NAMES: tuple[str, ...] = (
    "linkedin",
    "indeed",
    "zip_recruiter",
    "glassdoor",
)

DEFAULT_GREENHOUSE_BOARD_TOKENS: tuple[str, ...] = (
    "airbnb",
    "coinbase",
    "doordash",
    "dropbox",
    "databricks",
    "elastic",
    "figma",
    "hashicorp",
    "notion",
    "openai",
    "pinterest",
    "plaid",
    "reddit",
    "robinhood",
    "shopify",
    "snowflake",
    "stripe",
    "twilio",
    "vercel",
    "waymo",
)

DEFAULT_LEVER_COMPANIES: tuple[str, ...] = (
    "netflix",
    "tesla",
    "uber",
    "canva",
    "linear",
    "retool",
    "benchling",
    "headway",
    "nextdoor",
    "postman",
    "freshworks",
)


def _csv_or_default(value: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    parsed = tuple(item.strip() for item in (value or "").split(",") if item.strip())
    return parsed or fallback


def greenhouse_board_tokens() -> tuple[str, ...]:
    return _csv_or_default(settings.GREENHOUSE_BOARD_TOKENS, DEFAULT_GREENHOUSE_BOARD_TOKENS)


def lever_companies() -> tuple[str, ...]:
    return _csv_or_default(settings.LEVER_COMPANIES, DEFAULT_LEVER_COMPANIES)


def jobspy_site_names() -> tuple[str, ...]:
    return _csv_or_default(settings.JOBSPY_SITE_NAMES, DEFAULT_JOBSPY_SITE_NAMES)


def _default_queries_for_source(source_name: str) -> tuple[str, ...]:
    # Query APIs rarely expose a true "all jobs" endpoint. Empty query first broadens retrieval.
    if source_name in {"adzuna", "the_muse", "usajobs"}:
        return ("",) + SEARCH_QUERIES
    return SEARCH_QUERIES


async def _log_ingestion_run(db: AsyncSession, tenant_id: UUID, source_name: str, inserted: int) -> None:
    db.add(
        SupervisorLog(
            tenant_id=tenant_id,
            event_type="ingestion_run",
            severity=SeverityEnum.info,
            payload={
                "source": source_name,
                "new_jobs": int(inserted),
                "ts": datetime.now(UTC).isoformat(),
            },
        )
    )
    await db.commit()


def _clean_role_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _to_role_variants(raw: str) -> list[str]:
    text = _clean_role_text(raw)
    if not text:
        return []

    # Normalize obvious abbreviations and common aliases.
    aliases: dict[str, str] = {
        "swe": "software engineer",
        "sde": "software engineer",
        "ml engineer": "machine learning engineer",
        "ai engineer": "machine learning engineer",
        "mle": "machine learning engineer",
        "data sci": "data scientist",
        "fullstack engineer": "full stack engineer",
        "dev ops engineer": "devops engineer",
    }
    text = aliases.get(text, text)

    out = [text]
    if "engineer" not in text and len(text.split()) <= 4:
        out.append(f"{text} engineer")
    return out


def _ranked_unique(values: list[str], limit: int) -> list[str]:
    scores: dict[str, int] = {}
    for value in values:
        for variant in _to_role_variants(value):
            scores[variant] = scores.get(variant, 0) + 1
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [role for role, _score in ranked[:limit]]


def derive_role_queries(
    profile: UserProfile | None,
    parsed_resume: ResumeParsedData | None,
    explicit_query: str | None = None,
    limit: int = 10,
) -> list[str]:
    """Derive role search queries from profile + parsed resume context."""

    candidates: list[str] = []
    if explicit_query and explicit_query.strip():
        candidates.append(explicit_query.strip())

    if profile is not None:
        candidates.extend([role for role in (profile.target_roles or []) if role])
        if profile.headline:
            candidates.append(profile.headline)

    if parsed_resume is not None:
        candidates.extend([title for title in (parsed_resume.primary_job_titles or []) if title])
        domain_aliases = {
            "software_engineering": "software engineer",
            "data_science": "data scientist",
            "data_engineering": "data engineer",
            "devops": "devops engineer",
            "security": "security engineer",
            "product": "product manager",
            "design": "product designer",
        }
        if parsed_resume.primary_domain:
            mapped = domain_aliases.get(parsed_resume.primary_domain.strip().lower())
            if mapped:
                candidates.append(mapped)

        skills_blob = " ".join((parsed_resume.skills_all or [])[:80]).lower()
        if any(k in skills_blob for k in ("python", "fastapi", "django", "flask")):
            candidates.append("python backend engineer")
        if any(k in skills_blob for k in ("machine learning", "tensorflow", "pytorch", "llm", "nlp")):
            candidates.append("machine learning engineer")
        if any(k in skills_blob for k in ("spark", "airflow", "dbt", "kafka", "etl")):
            candidates.append("data engineer")
        if any(k in skills_blob for k in ("react", "typescript", "next.js", "nextjs", "frontend")):
            candidates.append("frontend engineer")
        if any(k in skills_blob for k in ("kubernetes", "terraform", "aws", "gcp", "azure", "devops")):
            candidates.append("devops engineer")

    return _ranked_unique(candidates, limit=limit)


async def build_user_role_queries(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    resume_id: UUID | None = None,
    explicit_query: str | None = None,
    limit: int = 10,
) -> list[str]:
    """Build top role queries for one user using profile + latest parsed resume."""

    profile = (
        await db.execute(
            select(UserProfile).where(
                UserProfile.tenant_id == tenant_id,
                UserProfile.user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    parsed: ResumeParsedData | None = None
    if resume_id is not None:
        parsed = (
            await db.execute(
                select(ResumeParsedData).where(
                    ResumeParsedData.tenant_id == tenant_id,
                    ResumeParsedData.user_id == user_id,
                    ResumeParsedData.resume_id == resume_id,
                )
            )
        ).scalar_one_or_none()
    else:
        latest_resume = (
            await db.execute(
                select(Resume.id)
                .where(Resume.tenant_id == tenant_id, Resume.user_id == user_id, Resume.is_active.is_(True))
                .order_by(Resume.updated_at.desc(), Resume.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_resume is not None:
            parsed = (
                await db.execute(
                    select(ResumeParsedData).where(
                        ResumeParsedData.tenant_id == tenant_id,
                        ResumeParsedData.user_id == user_id,
                        ResumeParsedData.resume_id == latest_resume,
                    )
                )
            ).scalar_one_or_none()

    return derive_role_queries(profile, parsed, explicit_query=explicit_query, limit=limit)


async def build_tenant_role_queries(db: AsyncSession, tenant_id: UUID, limit: int = 10) -> list[str]:
    """Build aggregated role list for a tenant, used by periodic background ingestion."""

    candidates: list[str] = []
    profiles = (
        await db.execute(
            select(UserProfile.target_roles, UserProfile.headline).where(UserProfile.tenant_id == tenant_id)
        )
    ).all()
    for target_roles, headline in profiles:
        if target_roles:
            candidates.extend([role for role in target_roles if role])
        if headline:
            candidates.append(str(headline))

    parsed_rows = (
        await db.execute(
            select(ResumeParsedData.primary_job_titles, ResumeParsedData.primary_domain)
            .where(ResumeParsedData.tenant_id == tenant_id)
            .order_by(ResumeParsedData.parsed_at.desc().nullslast())
            .limit(100)
        )
    ).all()
    for primary_titles, primary_domain in parsed_rows:
        if primary_titles:
            candidates.extend([title for title in primary_titles if title])
        if primary_domain:
            candidates.append(str(primary_domain).replace("_", " "))

    return _ranked_unique(candidates, limit=limit)


async def expire_old_jobs(db: AsyncSession, tenant_id: UUID, days: int = 3650) -> int:
    """Delete jobs older than configured rolling window and remove them from Typesense."""

    if days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(select(Job.id).where(Job.tenant_id == tenant_id, Job.posted_at < cutoff))
    ids = [str(row[0]) for row in result.fetchall()]
    if ids:
        client = get_typesense_client()
        for job_id in ids:
            await delete_job_from_index(job_id, client)
    delete_result = await db.execute(delete(Job).where(Job.tenant_id == tenant_id, Job.posted_at < cutoff))
    await db.commit()
    return int(delete_result.rowcount or 0)


def _is_within_time_window(posted_at_ts: float | None, min_age_hours: int = 0, max_age_days: int = 5) -> bool:
    """Validate posting timestamp lies inside the desired freshness window."""

    if posted_at_ts is None:
        return False
    now = datetime.now(UTC)
    posted = datetime.fromtimestamp(posted_at_ts, tz=UTC)
    if posted > now:
        return False
    oldest = now - timedelta(days=max_age_days)
    newest = now - timedelta(hours=min_age_hours)
    return oldest <= posted <= newest if min_age_hours > 0 else oldest <= posted <= now


async def _ingest_from_adapter_pages(
    adapter: Any,
    db: AsyncSession,
    tenant_id: UUID,
    typesense_client: Any,
    chroma_client: Any,
    query: str,
    location: str | None,
    filters: dict[str, Any],
    max_pages: int,
    page_size: int,
    min_age_hours: int,
) -> int:
    """Ingest from a paged adapter query and return inserted count."""

    inserted = 0
    for page in range(1, max_pages + 1):
        try:
            seen = 0
            async for job in adapter.search(query=query, location=location, page=page, page_size=page_size, filters=filters):
                seen += 1
                if job.posted_at is None:
                    # Some providers omit posting timestamps; keep jobs searchable by assigning ingestion time.
                    job.posted_at = datetime.now(UTC).timestamp()
                if not _is_within_time_window(job.posted_at, min_age_hours=min_age_hours, max_age_days=5):
                    continue
                job.tenant_id = tenant_id
                if await upsert_job(job, db, typesense_client, chroma_client):
                    inserted += 1
            if seen == 0:
                break
        except Exception as exc:
            logger.warning(
                "ingestion_page_failed",
                extra={
                    "extra": {
                        "source": getattr(adapter, "SOURCE_NAME", "unknown"),
                        "query": query,
                        "location": location,
                        "page": page,
                        "filters": filters,
                        "error": str(exc),
                    }
                },
            )
            break
    return inserted


async def _ingest_source(
    source_name: str,
    db: AsyncSession,
    tenant_id: UUID,
    typesense_client: Any,
    chroma_client: Any,
    min_age_hours: int,
    search_queries: list[str] | tuple[str, ...] | None = None,
    location: str | None = "United States",
) -> int:
    """Run ingestion logic for one source with source-specific strategy."""

    adapter = ADAPTERS[source_name]
    inserted = 0

    if source_name == "remoteok":
        inserted += await _ingest_from_adapter_pages(
            adapter,
            db,
            tenant_id,
            typesense_client,
            chroma_client,
            query="",
            location=None,
            filters={},
            max_pages=1,
            page_size=200,
            min_age_hours=min_age_hours,
        )
        return inserted

    if source_name == "arbeitnow":
        inserted += await _ingest_from_adapter_pages(
            adapter,
            db,
            tenant_id,
            typesense_client,
            chroma_client,
            query="",
            location=None,
            filters={},
            max_pages=6,
            page_size=50,
            min_age_hours=min_age_hours,
        )
        return inserted

    if source_name == "greenhouse":
        for token in greenhouse_board_tokens():
            inserted += await _ingest_from_adapter_pages(
                adapter,
                db,
                tenant_id,
                typesense_client,
                chroma_client,
                query="",
                location=None,
                filters={"board_token": token},
                max_pages=1,
                page_size=200,
                min_age_hours=min_age_hours,
            )
        return inserted

    if source_name == "lever":
        for company in lever_companies():
            inserted += await _ingest_from_adapter_pages(
                adapter,
                db,
                tenant_id,
                typesense_client,
                chroma_client,
                query="",
                location=None,
                filters={"company": company},
                max_pages=1,
                page_size=200,
                min_age_hours=min_age_hours,
            )
        return inserted

    if source_name == "jobspy":
        queries = tuple(search_queries) if search_queries else _default_queries_for_source(source_name)
        for query in queries:
            for site_name in jobspy_site_names():
                inserted += await _ingest_from_adapter_pages(
                    adapter,
                    db,
                    tenant_id,
                    typesense_client,
                    chroma_client,
                    query=query,
                    location=location or "United States",
                    filters={"site_name": site_name, "indeed_country": "USA"},
                    max_pages=1,
                    page_size=100,
                    min_age_hours=min_age_hours,
                )
        return inserted

    # API-driven broad searches.
    queries = tuple(search_queries) if search_queries else _default_queries_for_source(source_name)
    for query in queries:
        inserted += await _ingest_from_adapter_pages(
            adapter,
            db,
            tenant_id,
            typesense_client,
            chroma_client,
            query=query,
            location=location or "United States",
            filters={},
            max_pages=2,
            page_size=50,
            min_age_hours=min_age_hours,
        )
    return inserted


async def run_ingestion_for_sources(
    db: AsyncSession,
    tenant_id: UUID,
    source_names: list[str],
    min_age_hours: int = 0,
    search_queries: list[str] | tuple[str, ...] | None = None,
    location: str | None = "United States",
) -> dict[str, int]:
    """Run one ingestion cycle for explicit sources and return per-source insert counts."""

    typesense_client = get_typesense_client()
    chroma_client = chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT)

    output: dict[str, int] = {}
    for source_name in source_names:
        adapter = ADAPTERS.get(source_name)
        if adapter is None:
            logger.warning("unknown_ingestion_source", extra={"extra": {"source": source_name}})
            output[source_name] = 0
            continue
        inserted = await _ingest_source(
            source_name=source_name,
            db=db,
            tenant_id=tenant_id,
            typesense_client=typesense_client,
            chroma_client=chroma_client,
            min_age_hours=min_age_hours,
            search_queries=search_queries,
            location=location,
        )
        output[source_name] = inserted
        await _log_ingestion_run(db, tenant_id, source_name, inserted)
    return output


async def run_default_ingestion_cycle(db: AsyncSession, tenant_id: UUID) -> dict[str, int]:
    """Run the default source set and expire stale jobs first."""

    expired = await expire_old_jobs(db, tenant_id, days=settings.JOB_RETENTION_DAYS)
    result = await run_ingestion_for_sources(db, tenant_id, list(DEFAULT_INGESTION_SOURCES), min_age_hours=0)
    result["expired"] = expired
    return result


async def run_personalized_ingestion_cycle(
    db: AsyncSession,
    tenant_id: UUID,
    role_queries: list[str],
    location_country: str = "United States",
    source_names: list[str] | None = None,
) -> dict[str, int]:
    """Run role-targeted ingestion to keep personalized jobs flowing into DB."""

    cleaned_queries = [q.strip() for q in role_queries if q and q.strip()]
    if not cleaned_queries:
        return {}
    sources = source_names or list(PERSONALIZED_INGESTION_SOURCES)
    return await run_ingestion_for_sources(
        db,
        tenant_id,
        sources,
        min_age_hours=0,
        search_queries=cleaned_queries[:10],
        location=location_country or "United States",
    )


async def periodic_ingestion_loop(session_factory: Any, stop_event: asyncio.Event, interval_seconds: int = 7200) -> None:
    """Continuously ingest jobs for all active tenants until shutdown."""

    last_personalized_run: dict[UUID, datetime] = {}

    # Delay first full ingestion cycle to keep startup and health checks responsive.
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass

        started = datetime.now(UTC).isoformat()
        try:
            async with session_factory() as db:
                from db.models.tenant import Tenant

                tenants_result = await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True)))
                tenant_ids = [row[0] for row in tenants_result.fetchall()]
                for tenant_id in tenant_ids:
                    cycle = await run_default_ingestion_cycle(db, tenant_id)
                    role_queries: list[str] = []
                    personalized_cycle: dict[str, int] = {}
                    last_run = last_personalized_run.get(tenant_id)
                    should_run_personalized = (
                        last_run is None or (datetime.now(UTC) - last_run).total_seconds() >= 7200
                    )
                    if should_run_personalized:
                        role_queries = await build_tenant_role_queries(db, tenant_id, limit=5)
                        if role_queries:
                            # Keep periodic role refresh lightweight to avoid impacting API responsiveness.
                            personalized_cycle = await run_personalized_ingestion_cycle(
                                db,
                                tenant_id,
                                role_queries,
                                location_country="United States",
                                source_names=list(DEFAULT_INGESTION_SOURCES),
                            )
                            last_personalized_run[tenant_id] = datetime.now(UTC)
                    logger.info(
                        "ingestion_cycle_complete",
                        extra={
                            "extra": {
                                "tenant_id": str(tenant_id),
                                "result": cycle,
                                "personalized_result": personalized_cycle,
                                "role_queries": role_queries,
                                "started": started,
                            }
                        },
                    )
        except Exception:
            logger.exception("periodic_ingestion_failed")
