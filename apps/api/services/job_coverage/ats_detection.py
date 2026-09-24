"""Automatic ATS platform detection for company careers pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class ATSDetectionResult:
    ats_type: str
    careers_url: str
    confidence: float


_SIGNATURES: dict[str, tuple[str, ...]] = {
    "workday": ("/wd1.myworkdayjobs.com", "myworkdayjobs.com"),
    "icims": ("/icims.com/jobs", "icims.com/jobs"),
    "smartrecruiters": ("smartrecruiters.com",),
    "ashby": ("jobs.ashbyhq.com",),
    "greenhouse": ("boards.greenhouse.io",),
    "lever": ("jobs.lever.co",),
    "bamboohr": ("bamboohr.com/careers",),
}

_URL_RE = re.compile(r"https?://[^\"'\s<>]+", re.IGNORECASE)


async def _download_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception:
        return ""


def _find_careers_url(base_url: str, html: str, signature: str) -> str:
    for candidate in _URL_RE.findall(html):
        if signature in candidate.lower():
            return candidate
    return base_url


async def detect_ats(company_url: str, html: str | None = None) -> ATSDetectionResult:
    """Detect ATS type and best careers URL for a company website."""

    url = (company_url or "").strip()
    haystack = url.lower()
    if html is None:
        html = await _download_html(url)
    full_text = f"{haystack}\n{(html or '').lower()}"

    best = ATSDetectionResult(ats_type="unknown", careers_url=url, confidence=0.0)
    for ats_type, signatures in _SIGNATURES.items():
        for signature in signatures:
            if signature in full_text:
                in_url = signature in haystack
                careers_url = _find_careers_url(url, html or "", signature)
                confidence = 0.95 if in_url else 0.8
                if confidence > best.confidence:
                    best = ATSDetectionResult(
                        ats_type=ats_type,
                        careers_url=careers_url,
                        confidence=confidence,
                    )
    return best
