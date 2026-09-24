"""Connector framework spanning Tier-1 APIs and Tier-2 ATS templates."""

from __future__ import annotations

import logging
from typing import Any

from adapters.base import BaseJobAdapter
from services.ingestion_service import build_adapter
from services.job_coverage.ats_scrapers import get_ats_scraper, supported_ats_types
from services.job_coverage.schema import JobPosting, from_normalized_job

logger = logging.getLogger(__name__)

TIER1_SOURCES: tuple[str, ...] = (
    "greenhouse",
    "lever",
    "usajobs",
    "arbeitnow",
    "remoteok",
    "adzuna",
)

TIER2_ATS_SOURCES: tuple[str, ...] = tuple(supported_ats_types())


def _as_adapter(source: str) -> BaseJobAdapter:
    adapter = build_adapter(source)
    if not isinstance(adapter, BaseJobAdapter):
        raise TypeError(f"Adapter for source '{source}' does not implement BaseJobAdapter")
    return adapter


async def fetch_tier1_jobs(
    source: str,
    *,
    query: str = "",
    location: str | None = None,
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 100,
) -> list[JobPosting]:
    if source not in TIER1_SOURCES:
        raise KeyError(source)
    adapter = _as_adapter(source)
    if hasattr(adapter, "validate_config") and not adapter.validate_config():
        await adapter.close()
        logger.warning("job_coverage_source_disabled", extra={"extra": {"source": source}})
        return []
    jobs: list[JobPosting] = []
    try:
        async for item in adapter.search(
            query=query,
            location=location,
            page=page,
            page_size=page_size,
            filters=filters or {},
        ):
            jobs.append(from_normalized_job(item))
    finally:
        await adapter.close()
    return jobs


async def fetch_tier2_jobs(
    ats_type: str,
    *,
    careers_url: str,
    company_domain: str,
    html: str | None = None,
) -> list[JobPosting]:
    if ats_type not in TIER2_ATS_SOURCES:
        raise KeyError(ats_type)
    scraper = get_ats_scraper(ats_type)
    return await scraper.scrape(careers_url=careers_url, company_domain=company_domain, html=html)
