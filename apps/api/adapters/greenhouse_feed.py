"""Greenhouse feed adapter."""

from __future__ import annotations

from datetime import datetime

from adapters.base import BaseJobAdapter, NormalizedJob


class GreenhouseFeedAdapter(BaseJobAdapter):
    """Adapter for Greenhouse public job board feeds."""

    SOURCE_NAME = "greenhouse"
    REFRESH_INTERVAL_SECONDS = 300

    async def _fetch_page(self, query: str, location: str | None, page: int, page_size: int, filters: dict) -> dict:
        board_token = str(filters.get("board_token") or "").strip()
        if not board_token:
            return {"jobs": []}
        resp = await self._client.get(
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs",
            params={"content": "true"},
        )
        resp.raise_for_status()
        payload = resp.json()
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        if query:
            q = query.lower()
            jobs = [j for j in jobs if q in str(j.get("title", "")).lower() or q in str(j.get("content", "")).lower()]
        return {"jobs": jobs[:page_size]}

    def normalize(self, raw: dict) -> NormalizedJob:
        location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), list) else []
        tags = [str(item.get("value")) for item in metadata if isinstance(item, dict) and item.get("value")]
        posted_at_ts: float | None = None
        updated_at = raw.get("updated_at")
        if isinstance(updated_at, str):
            try:
                posted_at_ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                posted_at_ts = None

        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("absolute_url") or ""),
            title=str(raw.get("title") or "Untitled"),
            company=str(raw.get("company_name") or "Unknown"),
            description=raw.get("content"),
            url=str(raw.get("absolute_url") or ""),
            location_city=location.get("name"),
            remote="remote" in str(location.get("name") or "").lower(),
            tags=tags,
            posted_at=posted_at_ts,
            raw_json=raw,
        )
