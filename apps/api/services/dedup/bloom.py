"""Persistent Bloom filter helpers for exact dedup pre-checks."""

from __future__ import annotations

import hashlib

from bloom_filter2 import BloomFilter

_BLOOM: BloomFilter | "_InMemoryBloomFilter" | None = None


class _InMemoryBloomFilter:
    """Minimal in-memory fallback used when persistent Bloom init fails."""

    def __init__(self) -> None:
        self._values: set[str] = set()

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in self._values

    def add(self, item: str) -> None:
        self._values.add(item)


def get_bloom() -> BloomFilter | _InMemoryBloomFilter:
    """Return singleton Bloom filter with safe runtime fallback."""

    global _BLOOM
    if _BLOOM is None:
        try:
            # NOTE: file-backed init can raise and then emit noisy __del__ errors
            # in bloom-filter2; use in-memory backend for stable workers/API reloads.
            _BLOOM = BloomFilter(max_elements=10_000_000, error_rate=0.001)
        except Exception:
            _BLOOM = _InMemoryBloomFilter()
    return _BLOOM


def make_exact_fingerprint(source: str, source_id: str) -> str:
    """Build exact dedup fingerprint from source/source_id."""

    return hashlib.sha256(f"{source}:{source_id}".encode("utf-8")).hexdigest()


def is_exact_seen(fingerprint: str) -> bool:
    """Return True when the fingerprint already exists in Bloom filter."""

    return fingerprint in get_bloom()


def mark_exact_seen(fingerprint: str) -> None:
    """Store a fingerprint in the Bloom filter."""

    get_bloom().add(fingerprint)
