"""Unified job posting schema for the Job Coverage Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adapters.base import NormalizedJob


class JobPosting(BaseModel):
    """Connector-neutral job record shape."""

    model_config = ConfigDict(extra="ignore")

    source: str
    source_id: str
    company: str
    title: str
    location: str | None = None
    remote_type: str = "unknown"
    description: str | None = None
    salary_range: str | None = None
    employment_type: str = "unknown"
    experience_level: str = "unknown"
    skills: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    job_url: str
    raw: dict[str, Any] | None = None

    def identity_key(self, tenant_id: UUID) -> str:
        return f"{tenant_id}:{self.source}:{self.source_id}"

    def fuzzy_key(self) -> str:
        day = self.posted_at.date().isoformat() if self.posted_at else ""
        return "|".join(
            [
                (self.company or "").strip().lower(),
                (self.title or "").strip().lower(),
                (self.location or "").strip().lower(),
                day,
            ]
        )

    def content_hash(self) -> str:
        payload = "|".join(
            [
                self.source,
                self.source_id,
                self.company,
                self.title,
                self.location or "",
                self.job_url,
            ]
        )
        return sha1(payload.encode("utf-8")).hexdigest()

    def to_normalized_job(self, tenant_id: UUID) -> NormalizedJob:
        location = (self.location or "").strip()
        posted_at_ts = self.posted_at.replace(tzinfo=UTC).timestamp() if self.posted_at else datetime.now(UTC).timestamp()
        return NormalizedJob(
            tenant_id=tenant_id,
            source=self.source,
            source_id=self.source_id,
            title=self.title,
            company=self.company,
            description=self.description,
            url=self.job_url,
            location_city=location or None,
            remote=self.remote_type.lower() in {"remote", "hybrid_remote", "distributed"},
            salary_min=None,
            salary_max=None,
            salary_currency="USD",
            job_type=(self.employment_type or "unknown").lower().replace(" ", "_"),
            experience_level=(self.experience_level or "unknown").lower().replace(" ", "_"),
            tags=[s for s in self.skills if s],
            posted_at=posted_at_ts,
            raw_json=self.raw or {},
        )


def from_normalized_job(job: NormalizedJob) -> JobPosting:
    """Map legacy adapter output into JobPosting."""

    posted_at = datetime.fromtimestamp(job.posted_at, tz=UTC) if job.posted_at else None
    return JobPosting(
        source=job.source,
        source_id=job.source_id,
        company=job.company,
        title=job.title,
        location=job.location_city or job.location_state or job.location_country,
        remote_type="remote" if job.remote else "onsite",
        description=job.description,
        salary_range=None,
        employment_type=job.job_type,
        experience_level=job.experience_level,
        skills=list(job.tags or []),
        posted_at=posted_at,
        job_url=job.url,
        raw=job.raw_json,
    )
