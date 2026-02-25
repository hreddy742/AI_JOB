"""Lever feed adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from adapters.base import BaseJobAdapter, NormalizedJob


class LeverFeedAdapter(BaseJobAdapter):
    """Adapter for Lever postings feed."""

    SOURCE_NAME = "lever"
    REFRESH_INTERVAL_SECONDS = 300

    async def _fetch_page(self, query: str, location: str | None, page: int, page_size: int, filters: dict) -> dict:
        company = str(filters.get("company") or "").strip()
        if not company:
            return {"jobs": []}
        resp = await self._client.get(f"https://api.lever.co/v0/postings/{company}", params={"mode": "json"})
        resp.raise_for_status()
        payload = resp.json()
        jobs = payload if isinstance(payload, list) else []
        if query:
            q = query.lower()
            jobs = [j for j in jobs if q in str(j.get("text", "")).lower() or q in str(j.get("descriptionPlain", "")).lower()]
        return {"jobs": jobs[:page_size]}

    def normalize(self, raw: dict) -> NormalizedJob:
        categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
        posted_at_ts: float | None = None
        created_at = raw.get("createdAt")
        if isinstance(created_at, (int, float)) and created_at > 0:
            posted_at_ts = datetime.fromtimestamp(float(created_at) / 1000.0, tz=UTC).timestamp()
        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("hostedUrl") or ""),
            title=str(raw.get("text") or "Untitled"),
            company=str(raw.get("company") or "Unknown"),
            description=raw.get("descriptionPlain") or raw.get("description"),
            url=str(raw.get("hostedUrl") or ""),
            location_city=str(categories.get("location") or ""),
            remote="remote" in str(categories.get("location") or "").lower(),
            job_type=str(categories.get("commitment") or "unknown").lower().replace(" ", "_"),
            tags=[str(value) for value in categories.values() if value],
            posted_at=posted_at_ts,
            raw_json=raw,
        )
