"""JobSpy adapter with graceful fallback when dependency is unavailable."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from adapters.base import BaseJobAdapter, NormalizedJob

try:
    from jobspy import scrape_jobs
except Exception:  # pragma: no cover
    scrape_jobs = None


class JobSpyAdapter(BaseJobAdapter):
    """Adapter that reads jobs via python-jobspy."""

    SOURCE_NAME = "jobspy"
    REFRESH_INTERVAL_SECONDS = 1200
    calls_per_minute = 10

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value) if value is not None and str(value) != "" else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_tags(raw: dict[str, Any]) -> list[str]:
        source = raw.get("skills") or raw.get("job_function") or []
        if isinstance(source, str):
            source = [source]
        if not isinstance(source, list):
            return []
        return [str(tag) for tag in source if str(tag).strip()]

    @staticmethod
    def _normalize_job_type(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if "intern" in raw:
            return "internship"
        if "contract" in raw or "temp" in raw:
            return "contract"
        if "part" in raw:
            return "part_time"
        if "full" in raw or raw in {"permanent", "regular"}:
            return "full_time"
        return "unknown"

    @staticmethod
    def _normalize_experience(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if any(k in raw for k in ("executive", "director", "vp", "chief", "c-level")):
            return "executive"
        if any(k in raw for k in ("lead", "principal", "staff")):
            return "lead"
        if any(k in raw for k in ("senior", "sr")):
            return "senior"
        if any(k in raw for k in ("mid", "intermediate")):
            return "mid"
        if any(k in raw for k in ("entry", "junior", "jr", "new grad", "graduate")):
            return "entry"
        return "unknown"

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        if isinstance(value, dict):
            return {str(k): JobSpyAdapter._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [JobSpyAdapter._json_safe(v) for v in value]
        return str(value)

    async def _fetch_page(self, query: str, location: str | None, page: int, page_size: int, filters: dict[str, Any]) -> dict:
        if scrape_jobs is None:
            return {"jobs": []}

        site_name = str(filters.get("site_name") or "linkedin")
        wanted_results = max(1, int(page_size)) * max(1, int(page))

        # `scrape_jobs` is sync and can block for seconds; run it in a worker thread.
        data = await asyncio.to_thread(
            scrape_jobs,
            site_name=[site_name],
            search_term=query or "software engineer",
            location=location or "United States",
            results_wanted=wanted_results,
            country_indeed=(filters.get("indeed_country") or "USA"),
        )

        records: list[dict[str, Any]] = []
        if hasattr(data, "to_dict"):
            records = data.to_dict(orient="records")
        elif isinstance(data, list):
            records = [item for item in data if isinstance(item, dict)]

        start = (max(page, 1) - 1) * max(page_size, 1)
        end = start + max(page_size, 1)
        return {"jobs": records[start:end]}

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        title = str(raw.get("title") or raw.get("job_title") or "Untitled")
        company = str(raw.get("company") or raw.get("company_name") or "Unknown")
        url = str(raw.get("job_url") or raw.get("url") or raw.get("job_url_direct") or "")
        location = str(raw.get("location") or raw.get("job_location") or "")
        location_lower = location.lower()
        country = str(raw.get("country") or raw.get("location_country") or "US")
        state = str(raw.get("state") or raw.get("location_state") or "")
        city = str(raw.get("city") or raw.get("location_city") or "")
        posted_at_ts = None
        posted = raw.get("date_posted")
        if isinstance(posted, datetime):
            posted_at_ts = posted.replace(tzinfo=posted.tzinfo or UTC).timestamp()
        elif isinstance(posted, str):
            try:
                posted_at_ts = datetime.fromisoformat(posted.replace("Z", "+00:00")).timestamp()
            except ValueError:
                posted_at_ts = None

        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("job_id") or url or f"{company}:{title}"),
            title=title,
            company=company,
            description=str(raw.get("description") or raw.get("job_description") or ""),
            url=url,
            location_city=city or location,
            location_state=state,
            location_country=country,
            remote=bool("remote" in location_lower or raw.get("is_remote") is True),
            salary_min=self._to_float(raw.get("min_amount")),
            salary_max=self._to_float(raw.get("max_amount")),
            salary_currency=str(raw.get("currency") or "USD"),
            job_type=self._normalize_job_type(raw.get("job_type")),
            experience_level=self._normalize_experience(raw.get("seniority_level")),
            tags=self._normalize_tags(raw),
            posted_at=posted_at_ts,
            raw_json=self._json_safe(raw),
        )
