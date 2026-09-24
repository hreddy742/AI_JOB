"""File-upload helpers for Browser Agent V1."""

from __future__ import annotations

from pathlib import Path


def validate_upload_path(path: str | None) -> str | None:
    """Return a normalized upload path when it exists."""

    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    return str(candidate)
