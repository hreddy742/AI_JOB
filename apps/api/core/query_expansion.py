"""Query expansion helpers loaded from YAML config."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_query_expansions(path: str | None = None) -> dict[str, list[str]]:
    """Load query expansion map from YAML file."""

    if path:
        target = Path(path)
    else:
        source = Path(__file__).resolve()
        candidates = [parent / "config" / "query_expansions.yml" for parent in source.parents]
        target = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    output: dict[str, list[str]] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, list):
                output[key.strip().lower()] = [str(item).strip() for item in value if str(item).strip()]
    return output


def expand_query(raw_query: str, expansions: dict[str, list[str]] | None = None) -> str:
    """Expand known shorthand query phrases."""

    text = (raw_query or "").strip()
    if not text:
        return text
    mapping = expansions if expansions is not None else load_query_expansions()
    lowered = text.lower()
    extras = list(mapping.get(lowered, []))
    for key, values in mapping.items():
        if key in lowered and key != lowered:
            extras.extend(values)
    extras = list(dict.fromkeys(extras))
    if not extras:
        return text
    return f"{text} {' '.join(extras)}".strip()
