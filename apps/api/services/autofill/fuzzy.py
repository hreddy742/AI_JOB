"""Lightweight fuzzy matching helpers for ATS field option selection."""

from __future__ import annotations

import re
from dataclasses import dataclass


def _normalize(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def levenshtein_distance(a: str, b: str) -> int:
    """Compute Levenshtein distance using dynamic programming."""

    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def similarity_ratio(a: str, b: str) -> float:
    """Return normalized similarity ratio in [0, 1]."""

    na = _normalize(a)
    nb = _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Cheap containment boost for common ATS suffix/prefix variants.
    if na in nb or nb in na:
        shorter = min(len(na), len(nb))
        longer = max(len(na), len(nb))
        return max(0.80, shorter / max(longer, 1))
    dist = levenshtein_distance(na, nb)
    return max(0.0, 1.0 - (dist / max(len(na), len(nb), 1)))


@dataclass(frozen=True)
class FuzzyMatch:
    value: str
    score: float


def best_fuzzy_match(
    target: str,
    options: list[str],
    *,
    min_score: float = 0.62,
) -> FuzzyMatch | None:
    """Return best fuzzy match for target from options."""

    if not target or not options:
        return None
    scored = [
        FuzzyMatch(value=option, score=similarity_ratio(target, option))
        for option in options
        if option and option.strip()
    ]
    if not scored:
        return None
    best = max(scored, key=lambda item: item.score)
    if best.score < min_score:
        return None
    return best
