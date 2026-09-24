"""ARQ queue names used across workers and enqueue paths."""

from __future__ import annotations

QUEUE_RESUME = "arq:queue:resume"
QUEUE_TAILORING = "arq:queue:tailoring"
QUEUE_AUTOMATION = "arq:queue:automation"
QUEUE_CAMPAIGN = "arq:queue:campaign"
QUEUE_REFERRAL = "arq:queue:referral"
QUEUE_EMBEDDING = "arq:queue:embedding"
QUEUE_JOB_REQUIREMENTS = "arq:queue:job_requirements"
QUEUE_JOB_DETAIL_ENRICHMENT = "arq:queue:job_detail_enrichment"
QUEUE_JOB_COVERAGE = "arq:queue:job_coverage"
QUEUE_INGESTION = "arq:queue:ingestion"
QUEUE_NOTIFICATION = "arq:queue:notification"
QUEUE_BROWSER_AGENT_V1 = "arq:queue:browser_agent_v1"
QUEUE_BROWSER_AGENT_V1_MAINT = "arq:queue:browser_agent_v1_maint"
