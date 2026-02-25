"""Arbeitnow job adapter."""

from __future__ import annotations

from adapters.base import BaseJobAdapter, NormalizedJob


class ArbeitnowAdapter(BaseJobAdapter):
    """Adapter for Arbeitnow jobs API."""

    SOURCE_NAME = "arbeitnow"
    REFRESH_INTERVAL_SECONDS = 1800

    async def _fetch_page(self, query: str, location: str | None, page: int, page_size: int, filters: dict) -> dict:
        resp = await self._client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("data", []) if isinstance(data, dict) else []
        if query:
            q = query.lower()
            jobs = [j for j in jobs if q in str(j.get("title", "")).lower() or q in str(j.get("description", "")).lower()]
        return {"jobs": jobs[:page_size]}

    def normalize(self, raw: dict) -> NormalizedJob:
        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("slug") or raw.get("url") or ""),
            title=str(raw.get("title") or "Untitled"),
            company=str(raw.get("company_name") or "Unknown"),
            description=raw.get("description"),
            url=str(raw.get("url") or ""),
            location_city=str(raw.get("location") or ""),
            remote=bool(raw.get("remote") is True or "remote" in str(raw.get("location", "")).lower()),
            job_type="full_time",
            tags=[str(tag) for tag in (raw.get("tags") or [])],
            raw_json=raw,
        )
