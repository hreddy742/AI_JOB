"""RemoteOK job adapter."""

from __future__ import annotations

from adapters.base import BaseJobAdapter, NormalizedJob


class RemoteOKAdapter(BaseJobAdapter):
    """Adapter for RemoteOK API."""

    SOURCE_NAME = "remoteok"
    REFRESH_INTERVAL_SECONDS = 600

    async def _fetch_page(
        self,
        query: str,
        location: str | None,
        page: int,
        page_size: int,
        filters: dict,
    ) -> dict:
        resp = await self._client.get("https://remoteok.com/api")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            items = [item for item in data if isinstance(item, dict) and item.get("id")]
            if query:
                q = query.lower()
                items = [i for i in items if q in str(i.get("position", "")).lower() or q in str(i.get("description", "")).lower()]
            return {"jobs": items[:page_size]}
        return {"jobs": []}

    def normalize(self, raw: dict) -> NormalizedJob:
        tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
        return NormalizedJob(
            source=self.SOURCE_NAME,
            source_id=str(raw.get("id") or raw.get("slug") or ""),
            title=str(raw.get("position") or raw.get("role") or "Untitled"),
            company=str(raw.get("company") or "Unknown"),
            description=raw.get("description"),
            url=str(raw.get("url") or raw.get("apply_url") or ""),
            location_city=str(raw.get("location") or "Remote"),
            location_country="",
            remote=True,
            salary_min=float(raw["salary_min"]) if raw.get("salary_min") is not None else None,
            salary_max=float(raw["salary_max"]) if raw.get("salary_max") is not None else None,
            tags=[str(tag) for tag in tags],
            posted_at=float(raw.get("epoch") or 0) or None,
            raw_json=raw,
        )
