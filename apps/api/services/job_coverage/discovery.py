"""Company seed discovery for ATS-targeted crawling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.company_crawl_target import CompanyCrawlTarget
from services.job_coverage.ats_detection import detect_ats


@dataclass(slots=True)
class CompanySeed:
    company: str
    domain: str


FORTUNE500_SEEDS: tuple[CompanySeed, ...] = (
    CompanySeed("Walmart", "walmart.com"),
    CompanySeed("Amazon", "amazon.jobs"),
    CompanySeed("Apple", "apple.com"),
    CompanySeed("Microsoft", "microsoft.com"),
)

YC_SEEDS: tuple[CompanySeed, ...] = (
    CompanySeed("Stripe", "stripe.com"),
    CompanySeed("Airbnb", "airbnb.com"),
    CompanySeed("Dropbox", "dropbox.com"),
)

TECH_SEEDS: tuple[CompanySeed, ...] = (
    CompanySeed("Databricks", "databricks.com"),
    CompanySeed("Snowflake", "snowflake.com"),
    CompanySeed("Cloudflare", "cloudflare.com"),
)

STARTUP_SEEDS: tuple[CompanySeed, ...] = (
    CompanySeed("Vercel", "vercel.com"),
    CompanySeed("Notion", "notion.so"),
    CompanySeed("Figma", "figma.com"),
)


def default_seed_set() -> list[CompanySeed]:
    return list(FORTUNE500_SEEDS + YC_SEEDS + TECH_SEEDS + STARTUP_SEEDS)


def guess_careers_url(domain: str) -> str:
    normalized = domain.strip().lower()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        base = normalized
    else:
        base = f"https://{normalized}"
    return f"{base.rstrip('/')}/careers"


async def upsert_company_target(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    company: str,
    domain: str,
    careers_url: str,
    ats_type: str,
    crawl_frequency_minutes: int,
) -> CompanyCrawlTarget:
    existing = (
        await db.execute(
            select(CompanyCrawlTarget).where(
                CompanyCrawlTarget.tenant_id == tenant_id,
                CompanyCrawlTarget.company == company,
                CompanyCrawlTarget.careers_url == careers_url,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.ats_type = ats_type
        existing.crawl_frequency_minutes = crawl_frequency_minutes
        existing.last_checked_at = datetime.now(UTC)
        return existing

    row = CompanyCrawlTarget(
        tenant_id=tenant_id,
        company=company,
        domain=domain,
        careers_url=careers_url,
        ats_type=ats_type,
        crawl_frequency_minutes=max(crawl_frequency_minutes, 15),
        is_active=True,
        last_checked_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def discover_company_targets(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    seeds: list[CompanySeed] | None = None,
    max_companies: int = 200,
) -> list[CompanyCrawlTarget]:
    source = seeds or default_seed_set()
    output: list[CompanyCrawlTarget] = []
    for seed in source[:max_companies]:
        careers_url = guess_careers_url(seed.domain)
        detection = await detect_ats(careers_url)
        domain = urlparse(careers_url).netloc or seed.domain
        target = await upsert_company_target(
            db,
            tenant_id=tenant_id,
            company=seed.company,
            domain=domain,
            careers_url=detection.careers_url or careers_url,
            ats_type=detection.ats_type,
            crawl_frequency_minutes=60 if detection.confidence >= 0.8 else 240,
        )
        output.append(target)
    await db.commit()
    return output
