"""The Muse job adapter."""

from __future__ import annotations

from datetime import datetime

from adapters.base import BaseJobAdapter, NormalizedJob


class TheMuseAdapter(BaseJobAdapter):
    """Adapter for The Muse API."""

    SOURCE_NAME = "the_muse"
    REFRESH_INTERVAL_SECONDS = 3600

    async def _fetch_page(self, query: str, location: str | None, page: int, page_size: int, filters: dict) -> dict:
        params = {"page": page, "descending": True}
        if query:
            params["category"] = query
        if location:
            params["location"] = location
        resp = await self._client.get("https://www.themuse.com/api/public/jobs", params=params)
        resp.raise_for_status()
        return resp.json()

    def normalize(self, raw: dict) -> NormalizedJob:
        locations = raw.get("locations") or []
        company = raw.get("company") if isinstance(raw.get("company"), dict) else {}
        publication_date = raw.get("publication_date")
        posted_at_ts: float | None = None
        if isinstance(publication_date, str):
            try:
                posted_at_ts = datetime.fromisoformat(publication_date.replace("Z", "+00:00")).timestamp()
            except ValueError:
                posted_at_ts = None

        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("refs", {}).get("landing_page") or ""),
            title=str(raw.get("name") or "Untitled"),
            company=str(company.get("name") or "Unknown"),
            description=raw.get("contents"),
            url=str((raw.get("refs") or {}).get("landing_page") or ""),
            location_city=str(locations[0].get("name")) if locations else None,
            remote=False,
            job_type="unknown",
            tags=[str(level.get("name")) for level in (raw.get("levels") or []) if isinstance(level, dict)],
            posted_at=posted_at_ts,
            raw_json=raw,
        )
