from __future__ import annotations

import hashlib

from adapters.base import NormalizedJob
from services.job_service import generate_fingerprint


def test_generate_fingerprint_is_stable() -> None:
    job = NormalizedJob(
        source="remoteok",
        source_id="123",
        title="Python Engineer",
        company="Acme",
        url="https://example.com/jobs/123",
    )
    fp1 = generate_fingerprint(job)
    fp2 = generate_fingerprint(job)
    assert fp1 == fp2
    assert fp1 == hashlib.md5("remoteok|123|python engineer|acme|https://example.com/jobs/123".encode("utf-8")).hexdigest()


def test_generate_fingerprint_changes_on_source_id_change() -> None:
    job_a = NormalizedJob(source="remoteok", source_id="123", title="Python Engineer", company="Acme", url="https://example.com/jobs/123")
    job_b = NormalizedJob(source="remoteok", source_id="456", title="Python Engineer", company="Acme", url="https://example.com/jobs/123")
    assert generate_fingerprint(job_a) != generate_fingerprint(job_b)
