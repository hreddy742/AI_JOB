"""Job schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    """Shared job fields."""

    source: str
    source_id: str
    title: str
    company: str
    description: str | None = None
    url: str
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None
    remote: bool = False
    sponsorship_score: float = 0.5
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str = "USD"
    job_type: str = "unknown"
    experience_level: str = "unknown"
    tags: list[str] = []
    posted_at: datetime | None = None
    expires_at: datetime | None = None


class JobResponse(JobBase):
    """Job response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    fingerprint: str
    ingested_at: datetime
    last_seen_at: datetime
    is_active: bool


class JobSearchResponse(BaseModel):
    """Typesense search result wrapper."""

    items: list[dict]
    total: int
    page: int
    page_size: int
    facets: list[dict]
    refresh_started: bool = False
