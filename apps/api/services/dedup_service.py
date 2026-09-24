"""Bloom + MinHash deduplication helpers."""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Iterable

from services.dedup.bloom import get_bloom as _get_bloom

try:
    from bloom_filter2 import BloomFilter
except Exception:  # pragma: no cover - fallback for constrained environments
    class BloomFilter:  # type: ignore[no-redef]
        def __init__(self, max_elements: int = 10_000_000, error_rate: float = 0.001) -> None:
            self._set: set[str] = set()

        def __contains__(self, item: object) -> bool:
            return isinstance(item, str) and item in self._set

        def add(self, item: str) -> None:
            self._set.add(item)

try:
    from datasketch import MinHash, MinHashLSH
except Exception:  # pragma: no cover - fallback for constrained environments
    class MinHash:  # type: ignore[no-redef]
        def __init__(self, num_perm: int = 128) -> None:
            self.tokens: set[str] = set()

        def update(self, value: bytes) -> None:
            self.tokens.add(value.decode("utf-8"))

        def jaccard(self, other: "MinHash") -> float:
            if not self.tokens or not other.tokens:
                return 0.0
            return len(self.tokens & other.tokens) / len(self.tokens | other.tokens)

    class MinHashLSH:  # type: ignore[no-redef]
        def __init__(self, threshold: float = 0.75, num_perm: int = 128) -> None:
            self.entries: dict[str, MinHash] = {}
            self.threshold = threshold

        def query(self, signature: MinHash) -> list[str]:
            return [key for key, value in self.entries.items() if signature.jaccard(value) >= self.threshold]

        def insert(self, key: str, signature: MinHash) -> None:
            self.entries[key] = signature

COMPANY_ALIASES = {
    "google llc": "google",
    "google inc": "google",
    "alphabet": "google",
}


def normalize_company(name: str) -> str:
    """Normalize company aliases to a canonical token."""

    base = " ".join((name or "").lower().split())
    return COMPANY_ALIASES.get(base, base)


def source_fingerprint(source: str, source_id: str) -> str:
    """Build source-specific fingerprint."""

    return hashlib.sha256(f"{source}:{source_id}".encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def get_bloom_filter() -> BloomFilter:
    """Return process-wide Bloom filter for exact source-key precheck."""

    return _get_bloom()


def tokenize_for_minhash(text: str) -> list[str]:
    """Tokenize text into stable terms."""

    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


def normalized_job_text(title: str, company: str, location: str, description: str) -> str:
    """Normalize fields used for cross-source near duplicate matching."""

    return " ".join(
        [
            (title or "").strip().lower(),
            normalize_company(company),
            (location or "").strip().lower(),
            (description or "")[:300].strip().lower(),
        ]
    ).strip()


def build_minhash(tokens: Iterable[str], num_perm: int = 128) -> MinHash:
    """Create MinHash sketch from text tokens."""

    sketch = MinHash(num_perm=num_perm)
    for token in tokens:
        sketch.update(token.encode("utf-8"))
    return sketch


class MinHashDeduplicator:
    """In-memory MinHash LSH index for near-duplicate detection."""

    def __init__(self, threshold: float = 0.75, num_perm: int = 128) -> None:
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.signatures: dict[str, MinHash] = {}

    def find_near_duplicate(self, doc_id: str, normalized_text: str) -> tuple[str | None, float]:
        """Return canonical match id and similarity if near-duplicate exists."""

        signature = build_minhash(tokenize_for_minhash(normalized_text), num_perm=self.num_perm)
        candidates = self.lsh.query(signature)
        best_id: str | None = None
        best_score = 0.0
        for candidate in candidates:
            candidate_sig = self.signatures.get(candidate)
            if candidate_sig is None:
                continue
            score = signature.jaccard(candidate_sig)
            if score > best_score:
                best_id = candidate
                best_score = score
        if best_id is not None:
            return best_id, best_score
        self.lsh.insert(doc_id, signature)
        self.signatures[doc_id] = signature
        return None, 0.0
