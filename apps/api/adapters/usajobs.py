"""USAJobs adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from adapters.base import BaseJobAdapter, NormalizedJob


class USAJobsAdapter(BaseJobAdapter):
    """Adapter for USAJobs API."""

    SOURCE_NAME = "usajobs"
    REFRESH_INTERVAL_SECONDS = 3600

    async def _fetch_page(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {"Host": "data.usajobs.gov", "User-Agent": "apex-apply", "Authorization-Key": self.api_key or ""}
        params: dict[str, Any] = {"Page": page, "ResultsPerPage": page_size, "Keyword": query}
        if location:
            params["LocationName"] = location
        resp = await self._client.get("https://data.usajobs.gov/api/search", headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _extract_items(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        sr = raw.get("SearchResult") if isinstance(raw.get("SearchResult"), dict) else {}
        items = sr.get("SearchResultItems") if isinstance(sr.get("SearchResultItems"), list) else []
        extracted: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("MatchedObjectDescriptor"), dict):
                extracted.append(item["MatchedObjectDescriptor"])
        return extracted

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        posted_at_ts: float | None = None
        if isinstance(raw.get("PositionStartDate"), str):
            try:
                posted_at_ts = datetime.fromisoformat(raw["PositionStartDate"].replace("Z", "+00:00")).timestamp()
            except ValueError:
                posted_at_ts = None

        locations = raw.get("PositionLocation") if isinstance(raw.get("PositionLocation"), list) else []
        first_location = locations[0] if locations and isinstance(locations[0], dict) else {}

        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("PositionID") or raw.get("PositionURI") or ""),
            title=str(raw.get("PositionTitle") or "Untitled"),
            company=str(raw.get("OrganizationName") or "US Government"),
            description=raw.get("UserArea", {}).get("Details", {}).get("JobSummary") if isinstance(raw.get("UserArea"), dict) else None,
            url=str(raw.get("PositionURI") or ""),
            location_city=first_location.get("LocationName"),
            location_country="US",
            remote=False,
            salary_min=float(raw.get("PositionRemuneration", [{}])[0].get("MinimumRange")) if raw.get("PositionRemuneration") else None,
            salary_max=float(raw.get("PositionRemuneration", [{}])[0].get("MaximumRange")) if raw.get("PositionRemuneration") else None,
            salary_currency="USD",
            tags=[],
            posted_at=posted_at_ts,
            raw_json=raw,
        )
