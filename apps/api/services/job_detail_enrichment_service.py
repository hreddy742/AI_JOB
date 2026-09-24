"""Second-stage job detail enrichment for truncated source payloads."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select

from core.config import settings
from db.models.job import Job
from db.session import AsyncSessionFactory

HIGH_VOLUME_SOURCES: set[str] = {
    "adzuna",
    "careerjet",
    "jobspy",
    "hackernews_whos_hiring",
    "rss_feed",
}


def _clean_html_text(html: str) -> str:
    """Extract readable text from raw HTML without external parser dependencies."""

    if not html:
        return ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000]


def should_enrich_job(job: Job) -> bool:
    """Return True when a job is a candidate for detail-enrichment stage."""

    if not settings.ENABLE_JOB_DETAIL_ENRICHMENT:
        return False
    if not job.url:
        return False
    if not job.is_active:
        return False
    if str(job.source or "").lower() not in HIGH_VOLUME_SOURCES:
        return False
    current_len = len((job.description or "").strip())
    return current_len < int(settings.JOB_DETAIL_MIN_DESCRIPTION_CHARS)


async def _fetch_detail_text(url: str) -> str:
    """Fetch page and return extracted text snippet."""

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return _clean_html_text(resp.text)


async def enrich_job_details_batch(*, count: int | None = None) -> dict[str, int]:
    """Enrich a bounded batch of jobs with fuller page-derived descriptions."""

    limit = int(count or settings.JOB_DETAIL_ENRICHMENT_BATCH_SIZE)
    checked = 0
    enriched = 0
    failed = 0
    stale_before = datetime.now(UTC) - timedelta(days=2)

    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                select(Job)
                .where(Job.is_active.is_(True), Job.ingested_at >= stale_before)
                .order_by(Job.ingested_at.desc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        for job in rows:
            if not should_enrich_job(job):
                continue
            checked += 1
            try:
                detail = await _fetch_detail_text(str(job.url))
                current = (job.description or "").strip()
                if len(detail) > len(current) + 120:
                    job.description = detail
                    enriched += 1
                raw = dict(job.raw_json or {})
                raw["detail_enriched_at"] = datetime.now(UTC).isoformat()
                raw["detail_enrichment_status"] = "ok"
                job.raw_json = raw
            except Exception:
                failed += 1
                raw = dict(job.raw_json or {})
                raw["detail_enriched_at"] = datetime.now(UTC).isoformat()
                raw["detail_enrichment_status"] = "failed"
                job.raw_json = raw
        await db.commit()
    return {"checked": checked, "enriched": enriched, "failed": failed}
