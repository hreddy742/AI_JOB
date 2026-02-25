"""Adzuna job adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from adapters.base import BaseJobAdapter, NormalizedJob


class AdzunaAdapter(BaseJobAdapter):
    """Adapter for Adzuna Jobs API."""

    SOURCE_NAME = "adzuna"
    REFRESH_INTERVAL_SECONDS = 1800

    def __init__(self, api_key: str | None = None, app_id: str | None = None) -> None:
        super().__init__(api_key=api_key)
        self.app_id = app_id or ""

    async def _fetch_page(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key or not self.app_id:
            return {"results": []}
        params: dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.api_key,
            "what": query,
            "where": location or "",
            "results_per_page": page_size,
            "content-type": "application/json",
        }
        resp = await self._client.get(f"https://api.adzuna.com/v1/api/jobs/us/search/{page}", params=params)
        resp.raise_for_status()
        return resp.json()

    def normalize(self, raw: dict[str, Any]) -> NormalizedJob:
        created = raw.get("created")
        posted_at_ts: float | None = None
        if isinstance(created, str):
            try:
                posted_at_ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
            except ValueError:
                posted_at_ts = None

        location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("redirect_url") or ""),
            title=str(raw.get("title") or "Untitled"),
            company=str((raw.get("company") or {}).get("display_name") or "Unknown"),
            description=raw.get("description"),
            url=str(raw.get("redirect_url") or raw.get("url") or ""),
            location_city=location.get("display_name"),
            location_country="US",
            remote=False,
            salary_min=float(raw["salary_min"]) if raw.get("salary_min") is not None else None,
            salary_max=float(raw["salary_max"]) if raw.get("salary_max") is not None else None,
            salary_currency=str(raw.get("salary_currency") or "USD"),
            job_type="unknown",
            experience_level="unknown",
            tags=[],
            posted_at=posted_at_ts,
            raw_json=raw,
        )
