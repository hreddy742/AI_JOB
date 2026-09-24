"""Job Coverage Engine package."""

from services.job_coverage.ats_detection import ATSDetectionResult, detect_ats
from services.job_coverage.connector_catalog import (
    TIER1_SOURCES,
    TIER2_ATS_SOURCES,
    fetch_tier1_jobs,
    fetch_tier2_jobs,
)
from services.job_coverage.schema import JobPosting

__all__ = [
    "ATSDetectionResult",
    "JobPosting",
    "TIER1_SOURCES",
    "TIER2_ATS_SOURCES",
    "detect_ats",
    "fetch_tier1_jobs",
    "fetch_tier2_jobs",
]
