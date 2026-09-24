"""Reusable ATS scraper templates (Tier 2 connectors)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha1
from typing import Sequence
from urllib.parse import urljoin, urlparse

from services.job_coverage.schema import JobPosting

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover
    async_playwright = None


class BaseATSScraper:
    ats_type = "generic"
    listing_patterns: Sequence[str] = ("/jobs", "/job", "/careers")

    async def fetch_html(self, careers_url: str) -> str:
        if async_playwright is None:
            return ""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(careers_url, wait_until="domcontentloaded", timeout=30000)
            html = await page.content()
            await browser.close()
            return html

    def _extract_listing_links(self, careers_url: str, html: str) -> list[str]:
        links = re.findall(r"href=[\"']([^\"']+)[\"']", html or "", flags=re.IGNORECASE)
        out: list[str] = []
        for link in links:
            absolute = urljoin(careers_url, link)
            lower = absolute.lower()
            if any(p in lower for p in self.listing_patterns):
                out.append(absolute)
        return list(dict.fromkeys(out))

    def _title_from_url(self, link: str) -> str:
        slug = urlparse(link).path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ").strip()
        if not slug:
            return "Untitled"
        return slug.title()[:200]

    async def scrape(self, careers_url: str, company_domain: str, html: str | None = None) -> list[JobPosting]:
        page_html = html if html is not None else await self.fetch_html(careers_url)
        links = self._extract_listing_links(careers_url, page_html)
        postings: list[JobPosting] = []
        company_name = company_domain.replace("www.", "").split(".")[0].title()
        now = datetime.now(UTC)
        for link in links:
            source_id = sha1(link.encode("utf-8")).hexdigest()[:24]
            postings.append(
                JobPosting(
                    source=f"ats:{self.ats_type}",
                    source_id=source_id,
                    company=company_name,
                    title=self._title_from_url(link),
                    location=None,
                    remote_type="unknown",
                    description=None,
                    salary_range=None,
                    employment_type="unknown",
                    experience_level="unknown",
                    skills=[],
                    posted_at=now,
                    job_url=link,
                    raw={"careers_url": careers_url, "ats": self.ats_type},
                )
            )
        return postings


class WorkdayScraper(BaseATSScraper):
    ats_type = "workday"
    listing_patterns = ("/job/", "myworkdayjobs.com")


class ICIMSScraper(BaseATSScraper):
    ats_type = "icims"
    listing_patterns = ("/jobs/", "icims.com")


class SmartRecruitersScraper(BaseATSScraper):
    ats_type = "smartrecruiters"
    listing_patterns = ("smartrecruiters.com", "/jobs/")


class AshbyScraper(BaseATSScraper):
    ats_type = "ashby"
    listing_patterns = ("ashbyhq.com", "/job/")


class BambooHRScraper(BaseATSScraper):
    ats_type = "bamboohr"
    listing_patterns = ("bamboohr.com", "/careers/")


class GreenhouseCareersScraper(BaseATSScraper):
    ats_type = "greenhouse"
    listing_patterns = ("boards.greenhouse.io", "/jobs/")


class LeverCareersScraper(BaseATSScraper):
    ats_type = "lever"
    listing_patterns = ("jobs.lever.co", "/job/")


_SCRAPERS: dict[str, BaseATSScraper] = {
    "workday": WorkdayScraper(),
    "icims": ICIMSScraper(),
    "smartrecruiters": SmartRecruitersScraper(),
    "ashby": AshbyScraper(),
    "bamboohr": BambooHRScraper(),
    "greenhouse": GreenhouseCareersScraper(),
    "lever": LeverCareersScraper(),
}


def get_ats_scraper(ats_type: str) -> BaseATSScraper:
    return _SCRAPERS[ats_type]


def supported_ats_types() -> list[str]:
    return list(_SCRAPERS.keys())
