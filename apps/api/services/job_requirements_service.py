"""Background job-requirements analysis pipeline."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.normalizers import infer_role_family, normalize_work_mode
from core.config import settings
from db.models.job import Job
from db.models.job_requirement import JobRequirement
from db.session import AsyncSessionFactory
from services.search_service import get_typesense_client, index_job

# ---------------------------------------------------------------------------
# Typed skill taxonomy
# ---------------------------------------------------------------------------

PROGRAMMING_LANGUAGES: tuple[str, ...] = (
    "python", "java", "javascript", "typescript", "go", "golang", "rust",
    "scala", "ruby", "php", "c++", "c#", "swift", "kotlin", "r", "matlab",
    "julia", "haskell", "elixir", "erlang", "dart", "lua", "perl", "bash",
    "shell", "cobol", "fortran", "groovy", "clojure", "f#", "ocaml",
    "objective-c", "assembly",
)

FRAMEWORKS: tuple[str, ...] = (
    "react", "angular", "vue", "next.js", "nextjs", "django", "flask",
    "fastapi", "spring", "express", "rails", "laravel", "nestjs", "svelte",
    "remix", "nuxt", "htmx", "asp.net", ".net", "flutter", "ionic",
    "electron", "pytorch", "tensorflow", "keras", "jax", "scikit-learn",
    "hugging face", "langchain", "llamaindex", "transformers", "pandas",
    "numpy", "dask", "celery", "graphql", "grpc", "fastapi", "gin", "echo",
    "actix", "axum", "fiber",
)

DATABASES: tuple[str, ...] = (
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "cassandra", "dynamodb", "bigquery", "snowflake",
    "databricks", "redshift", "clickhouse", "neo4j", "aurora", "cockroachdb",
    "mariadb", "oracle", "mssql", "sql server", "pinecone", "weaviate",
    "chromadb", "qdrant", "milvus", "chroma", "supabase", "planetscale",
    "tidb", "couchdb", "hbase", "memcached", "druid", "presto", "trino",
)

CLOUD_TOOLS: tuple[str, ...] = (
    "aws", "gcp", "azure", "google cloud", "amazon web services",
    "s3", "ec2", "lambda", "ecs", "eks", "rds", "sqs", "sns", "cloudformation",
    "terraform", "pulumi", "ansible", "docker", "kubernetes", "k8s", "helm",
    "istio", "prometheus", "grafana", "datadog", "cloudwatch", "pagerduty",
    "vercel", "netlify", "heroku", "render", "fly.io", "github actions",
    "gitlab ci", "circle ci", "jenkins", "argocd", "vault", "consul",
    "airflow", "prefect", "dagster", "spark", "flink", "kafka", "kinesis",
    "dbt", "fivetran", "airbyte", "segment", "amplitude",
)

ML_AI_SKILLS: tuple[str, ...] = (
    "llm", "large language model", "gpt", "claude", "gemini", "llama",
    "mistral", "rag", "retrieval augmented generation", "vector search",
    "embedding", "fine-tuning", "lora", "qlora", "quantization", "vllm",
    "deep learning", "neural network", "reinforcement learning",
    "computer vision", "nlp", "natural language processing",
    "speech recognition", "gan", "diffusion model", "stable diffusion",
    "mlops", "mlflow", "wandb", "comet", "dvc", "feature store",
    "model serving", "triton", "bentoml", "ray serve", "langchain",
    "llamaindex", "autogen", "crewai", "langgraph", "openai", "anthropic",
    "xgboost", "lightgbm", "catboost", "a/b testing", "recommendation system",
    "object detection", "image classification", "text classification",
    "sentiment analysis", "named entity recognition", "transformers",
    "bert", "gpt-4", "llama 2", "mixtral", "hugging face",
)

CERTIFICATIONS: tuple[str, ...] = (
    "aws certified", "gcp certified", "google professional", "azure certified",
    "ckad", "cka", "cks", "comptia", "cissp", "cism", "ceh", "oscp",
    "pmp", "scrum master", "csm", "safe", "databricks certified",
    "snowflake pro", "tensorflow developer", "professional data engineer",
    "professional cloud architect", "solutions architect",
)

TOOL_KEYWORDS: tuple[str, ...] = (
    "jira", "figma", "tableau", "power bi", "snowflake", "databricks",
    "github", "gitlab", "jenkins", "kafka",
)

# Kept for backward compat (used in _extract_section_terms)
SKILL_KEYWORDS: tuple[str, ...] = PROGRAMMING_LANGUAGES + FRAMEWORKS + DATABASES + CLOUD_TOOLS

TECH_TOKEN_HINTS: tuple[str, ...] = (
    "sql", "aws", "gcp", "api", "k8", "docker", "kubernetes",
    "react", "node", "python", "java", "spark", "airflow", "terraform", "linux",
)

SKILL_CANONICAL_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
    "nextjs": "next.js",
    "google cloud": "gcp",
    "amazon web services": "aws",
    "k8s": "kubernetes",
}


def _content_hash(title: str, description: str) -> str:
    return hashlib.sha256(f"{title}\n{description}".encode("utf-8")).hexdigest()


def _normalize_list(values: list[str], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        item = (raw or "").strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _extract_years(text: str) -> int | None:
    matches = re.findall(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b", text, flags=re.IGNORECASE)
    years = [int(m) for m in matches if 0 < int(m) <= 40]
    return max(years) if years else None


def _extract_years_range(text: str) -> tuple[int | None, int | None]:
    """Return (min_years, max_years) from text like '3-5 years', '5+ years', 'at least 3 years'."""
    # "3-5 years" or "3 to 5 years"
    range_match = re.search(
        r"\b(\d{1,2})\s*[-–to]+\s*(\d{1,2})\s*(?:years?|yrs?)\b", text, re.IGNORECASE
    )
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        if 0 < lo <= hi <= 40:
            return lo, hi

    # "5+ years", "at least 5 years", "minimum 5 years"
    min_match = re.search(
        r"(?:at\s+least|minimum|min\.?\s*|>\s*)(\d{1,2})\+?\s*(?:years?|yrs?)\b", text, re.IGNORECASE
    )
    if min_match:
        val = int(min_match.group(1))
        if 0 < val <= 40:
            return val, None

    # "up to 3 years", "less than 3 years"
    max_match = re.search(
        r"(?:up\s+to|fewer\s+than|less\s+than|<\s*)(\d{1,2})\s*(?:years?|yrs?)\b", text, re.IGNORECASE
    )
    if max_match:
        val = int(max_match.group(1))
        if 0 < val <= 40:
            return None, val

    # Bare "X+ years" -> treat as min
    plus_match = re.search(r"\b(\d{1,2})\+\s*(?:years?|yrs?)\b", text, re.IGNORECASE)
    if plus_match:
        val = int(plus_match.group(1))
        if 0 < val <= 40:
            return val, None

    # Bare "X years" -> treat as min
    bare_matches = re.findall(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", text, re.IGNORECASE)
    years = [int(m) for m in bare_matches if 0 < int(m) <= 40]
    if years:
        return min(years), max(years) if len(years) > 1 else None

    return None, None


def _extract_salary_from_text(text: str) -> tuple[float | None, float | None, str, str]:
    """Extract salary from description text.

    Returns (min_salary, max_salary, period, raw_text).
    period is one of: 'hourly', 'monthly', 'yearly', 'unknown'.
    """
    # Clean text to ascii-ish
    lowered = text.lower()

    # Period detection helpers
    def _detect_period(context: str) -> str:
        ctx = context.lower()
        if re.search(r"\bper\s*hour\b|\bhourly\b|\b/\s*hr\b|\bph\b", ctx):
            return "hourly"
        if re.search(r"\bper\s*month\b|\bmonthly\b|\b/\s*mo\b|\bper\s*annum\b|\bannual\b|\byearly\b|\ba\s*year\b|\b/\s*yr\b|\bper\s*year\b", ctx):
            return "yearly"
        return "unknown"

    def _annualize(val: float, period: str) -> float:
        if period == "hourly":
            return val * 2080  # 40h x 52w
        if period == "monthly":
            return val * 12
        return val

    # Pattern: $X,000 - $Y,000 or $X - $Y k
    range_patterns = [
        # "$120,000 - $150,000" or "$120k - $150k"
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[k]?\s*[-–to]+\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[k]?",
        # "120,000 USD to 150,000 USD"
        r"(\d{1,3}(?:,\d{3})+)\s*(?:USD|CAD|GBP|EUR)?\s*[-–to]+\s*(\d{1,3}(?:,\d{3})+)\s*(?:USD|CAD|GBP|EUR)?",
    ]
    for pat in range_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_text = m.group(0)
            lo_str = m.group(1).replace(",", "")
            hi_str = m.group(2).replace(",", "")
            lo, hi = float(lo_str), float(hi_str)
            # Check for k suffix
            raw_lower = raw_text.lower()
            if "k" in raw_lower:
                if lo < 1000:
                    lo *= 1000
                if hi < 1000:
                    hi *= 1000
            period = _detect_period(lowered[max(0, lowered.find(raw_text.lower()[:10]) - 30):lowered.find(raw_text.lower()[:10]) + len(raw_text) + 30])
            if period == "unknown" and lo < 500:
                period = "hourly"  # Likely hourly if value is small
            lo = _annualize(lo, period)
            hi = _annualize(hi, period)
            if 10_000 <= lo <= 10_000_000 and lo <= hi:
                return lo, hi, period, raw_text

    # Single value: "$120,000" or "$120k"
    single_patterns = [
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[k]?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr|month|mo))?",
    ]
    for pat in single_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_text = m.group(0)
            val_str = m.group(1).replace(",", "")
            val = float(val_str)
            raw_lower = raw_text.lower()
            if "k" in raw_lower and val < 1000:
                val *= 1000
            period = _detect_period(lowered[max(0, lowered.find(raw_text.lower()[:8]) - 30):lowered.find(raw_text.lower()[:8]) + len(raw_text) + 30])
            if period == "unknown" and val < 500:
                period = "hourly"
            val = _annualize(val, period)
            if 10_000 <= val <= 10_000_000:
                return val, None, period, raw_text

    return None, None, "unknown", ""


def _extract_typed_skills(text: str) -> dict[str, list[str]]:
    """Extract skills categorized by type: languages, frameworks, databases, cloud, ml_ai, certs."""
    lowered = f" {text.lower()} "

    def _canonicalize_skill(term: str) -> str:
        return SKILL_CANONICAL_ALIASES.get(term.lower(), term.lower())

    def _find_terms(vocab: tuple[str, ...], limit: int = 12) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for term in vocab:
            # Boundary-aware match (word chars and dots/+ count as part of term)
            escaped = re.escape(term)
            pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
            if re.search(pattern, lowered, re.IGNORECASE):
                canonical = _canonicalize_skill(term)
                if canonical not in seen:
                    seen.add(canonical)
                    found.append(canonical)
                if len(found) >= limit:
                    break
        return found

    return {
        "programming_languages": _find_terms(PROGRAMMING_LANGUAGES, 10),
        "frameworks": _find_terms(FRAMEWORKS, 12),
        "databases": _find_terms(DATABASES, 10),
        "cloud_tools": _find_terms(CLOUD_TOOLS, 12),
        "ml_ai_skills": _find_terms(ML_AI_SKILLS, 12),
        "certifications": _find_terms(CERTIFICATIONS, 6),
    }


def _extract_education(text: str) -> str | None:
    lowered = text.lower()
    if "phd" in lowered or "doctorate" in lowered:
        return "phd"
    if "master" in lowered or "m.s." in lowered or "msc" in lowered:
        return "masters"
    if "bachelor" in lowered or "b.s." in lowered or "bs " in lowered:
        return "bachelors"
    if "associate" in lowered:
        return "associates"
    return None


def _extract_seniority(title: str, text: str) -> str:
    lowered = f"{title}\n{text}".lower()
    if any(k in lowered for k in ("principal", "staff", "architect", "director", "head of", "vp")):
        return "lead"
    if any(k in lowered for k in ("senior", "sr.")):
        return "senior"
    if any(k in lowered for k in ("manager", "lead ")):
        return "lead"
    if any(k in lowered for k in ("junior", "entry", "intern")):
        return "entry"
    if any(k in lowered for k in ("mid", "intermediate", "ii", "2")):
        return "mid"
    return "unknown"


def _extract_visa(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(no|not)\s+(visa\s+)?sponsor", lowered):
        return "no_sponsor"
    if re.search(r"\bvisa\s+sponsorship\s+(available|provided|offered)\b", lowered):
        return "sponsors"
    if re.search(r"\bwill\s+sponsor\b", lowered):
        return "sponsors"
    return "unknown"


def _extract_opt(text: str) -> tuple[str, str]:
    """Return (opt_allowed, stem_opt_allowed) as 'yes'/'no'/'unknown'."""
    lowered = text.lower()
    # Explicit denial
    if re.search(r"\b(no\s+opt|not\s+eligible.*opt|opt\s+not\s+accepted|cannot.*opt|no.*work\s+authorization)\b", lowered):
        return "no", "no"
    # OPT-friendly signals
    opt_ok = bool(re.search(r"\b(opt\s*(candidates?|holders?|students?|ok|welcome|accepted|eligible|considered))\b", lowered) or
                  re.search(r"\b(open\s+to\s+opt|opt\s+ok|opt\s+friendly|cpt\s+ok|cpt\s+welcome)\b", lowered))
    stem_ok = bool(re.search(r"\b(stem\s+opt|stem[-\s]opt\s+(ok|welcome|eligible|considered|accepted))\b", lowered))
    return ("yes" if opt_ok else "unknown"), ("yes" if stem_ok else "unknown")


def _extract_h1b(text: str) -> str:
    """Return h1b_possible as 'yes'/'no'/'unknown'."""
    lowered = text.lower()
    if re.search(r"\b(no\s+h[\-]?1b?|h[\-]?1b?\s+not\s+(available|sponsored|considered)|cannot\s+sponsor\s+h[\-]?1b?)\b", lowered):
        return "no"
    if re.search(r"\b(h[\-]?1b?\s+(transfer|sponsorship|visa)\s+(available|provided|possible|considered)|will\s+sponsor\s+h[\-]?1b?|h[\-]?1b?\s+ok|h[\-]?1b?\s+welcome)\b", lowered):
        return "yes"
    return "unknown"


def _extract_citizenship_flags(text: str) -> tuple[bool, bool]:
    """Return (us_citizens_only, security_clearance_required)."""
    lowered = text.lower()
    citizens_only = bool(re.search(
        r"\b(us\s+citizens?\s+only|u\.s\.\s+citizens?\s+required|must\s+be\s+(a\s+)?us\s+citizen|"
        r"green\s+card\s+holders?\s+only|permanent\s+residents?\s+only|authorized\s+to\s+work\s+in\s+the\s+us\s+without)\b",
        lowered
    ))
    clearance = bool(re.search(
        r"\b(security\s+clearance\s+required|must\s+have\s+(a\s+)?(?:active|current|valid)\s+(?:secret|ts|top\s*secret)|"
        r"(secret|ts\/sci|top\s+secret)\s+clearance\s+required|itar|clearance\s+eligible)\b",
        lowered
    ))
    return citizens_only, clearance


def _compute_ai_relevance(title: str, description: str) -> float:
    """Score 0-1 for how AI/ML-relevant the job is."""
    text = f"{title} {description[:800]}".lower()
    ai_terms = [
        "machine learning", "deep learning", "neural network", "llm", "gpt", "transformer",
        "nlp", "computer vision", "reinforcement learning", "generative ai", "diffusion",
        "pytorch", "tensorflow", "hugging face", "langchain", "rag", "vector", "embedding",
        "ai engineer", "ml engineer", "applied scientist", "data scientist",
    ]
    matches = sum(1 for term in ai_terms if term in text)
    return round(min(matches / 5.0, 1.0), 3)


def _extract_responsibilities(description: str) -> list[str]:
    # Lightweight bullet extraction for quick requirement faceting.
    lines = [line.strip(" -•\t") for line in description.splitlines()]
    bullets = [line for line in lines if len(line) >= 24]
    return bullets[:8]


def _extract_section_terms(description: str) -> tuple[list[str], list[str]]:
    lines = [line.strip(" -•\t") for line in (description or "").splitlines()]
    must_lines: list[str] = []
    nice_lines: list[str] = []
    section: str | None = None

    for line in lines:
        lowered = line.lower()
        if any(k in lowered for k in ("requirements", "required", "qualifications", "must have", "skills:")):
            section = "must"
            continue
        if any(k in lowered for k in ("nice to have", "preferred", "bonus", "plus:")):
            section = "nice"
            continue
        if not line:
            section = None
            continue
        if section == "must":
            must_lines.append(lowered)
        elif section == "nice":
            nice_lines.append(lowered)

    def _collect_terms(chunks: list[str]) -> list[str]:
        out: list[str] = []
        for chunk in chunks:
            for token in re.findall(r"[A-Za-z][A-Za-z0-9\+\#\.\-]{1,24}", chunk):
                t = token.lower()
                if t in SKILL_KEYWORDS:
                    out.append(t)
                    continue
                if any(h in t for h in TECH_TOKEN_HINTS):
                    out.append(t)
        return out

    return _collect_terms(must_lines), _collect_terms(nice_lines)


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"[\n\r]+|(?<=[\.\!\?])\s+", text or "")
    return [chunk.strip(" -\t•") for chunk in chunks if chunk and chunk.strip(" -\t•")]


def _find_evidence_sentence(text: str, term: str) -> str | None:
    escaped = re.escape(term.lower())
    pattern = re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)
    for sentence in _split_sentences(text):
        if pattern.search(sentence):
            return sentence[:280]
    return None


def _build_extraction_provenance(
    title: str,
    description: str,
    parsed: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    source_text = f"{title}\n{description or ''}"

    def _list_evidence(bucket: str, values: list[str]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for value in values:
            sentence = _find_evidence_sentence(source_text, value)
            if sentence:
                out.append({"bucket": bucket, "value": value, "evidence": sentence})
        return out

    years_evidence = _find_evidence_sentence(source_text, "years")
    salary_evidence = _find_evidence_sentence(source_text, "$") or _find_evidence_sentence(source_text, "salary")
    visa_evidence = (
        _find_evidence_sentence(source_text, "visa")
        or _find_evidence_sentence(source_text, "sponsor")
        or _find_evidence_sentence(source_text, "h1b")
    )

    return {
        "must_have_skills": _list_evidence("must_have_skills", parsed.get("must_have_skills") or []),
        "nice_to_have_skills": _list_evidence("nice_to_have_skills", parsed.get("nice_to_have_skills") or []),
        "tools_frameworks": _list_evidence("tools_frameworks", parsed.get("tools_frameworks") or []),
        "programming_languages": _list_evidence("programming_languages", parsed.get("programming_languages") or []),
        "frameworks": _list_evidence("frameworks", parsed.get("frameworks") or []),
        "databases": _list_evidence("databases", parsed.get("databases") or []),
        "cloud_tools": _list_evidence("cloud_tools", parsed.get("cloud_tools") or []),
        "ml_ai_skills": _list_evidence("ml_ai_skills", parsed.get("ml_ai_skills") or []),
        "certifications": _list_evidence("certifications", parsed.get("certifications") or []),
        "experience": (
            [{"bucket": "experience", "value": str(parsed.get("min_years_experience")), "evidence": years_evidence}]
            if parsed.get("min_years_experience") is not None and years_evidence
            else []
        ),
        "salary": (
            [{"bucket": "salary", "value": str(parsed.get("salary_text_raw") or ""), "evidence": salary_evidence}]
            if parsed.get("salary_text_raw") and salary_evidence
            else []
        ),
        "work_authorization": (
            [{"bucket": "work_authorization", "value": str(parsed.get("visa_sponsorship") or "unknown"), "evidence": visa_evidence}]
            if visa_evidence
            else []
        ),
    }


def _compute_ghost_risk(job: Job, parsed: dict[str, Any]) -> float:
    """Compute ghost-job risk score (0-1) from non-sensitive observable signals."""

    score = 0.0
    now = datetime.now(UTC)

    age_anchor = job.posted_at or job.ingested_at
    if age_anchor is not None:
        age_days = max((now - age_anchor).total_seconds() / 86400.0, 0.0)
        if age_days >= 60:
            score += 0.40
        elif age_days >= 30:
            score += 0.25
        elif age_days >= 14:
            score += 0.12

    if job.last_seen_at is not None:
        stale_seen_days = max((now - job.last_seen_at).total_seconds() / 86400.0, 0.0)
        if stale_seen_days >= 30:
            score += 0.25
        elif stale_seen_days >= 14:
            score += 0.12

    repost_count = int(getattr(job, "repost_count", 0) or 0)
    if repost_count <= 0:
        raw = job.raw_json if isinstance(job.raw_json, dict) else {}
        repost_raw = raw.get("repost_count") or raw.get("reposts") or raw.get("times_reposted") or 0
        try:
            repost_count = int(repost_raw or 0)
        except (TypeError, ValueError):
            repost_count = 0
    if repost_count >= 3:
        score += 0.30
    elif repost_count > 0:
        score += 0.15

    desc_len = len((job.description or "").strip())
    if desc_len < 160 and float(parsed.get("confidence") or 0.0) < 0.35:
        score += 0.10

    return round(min(score, 1.0), 3)


def analyze_job_requirements(title: str, description: str) -> dict[str, Any]:
    text = f"{title}\n{description or ''}"
    lowered = text.lower()

    # --- General skill extraction (legacy buckets, kept for backward compat) ---
    must_have = [skill for skill in PROGRAMMING_LANGUAGES + FRAMEWORKS + DATABASES + CLOUD_TOOLS
                 if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", lowered)]
    section_must, section_nice = _extract_section_terms(description or "")
    must_have.extend(section_must)
    nice_to_have = section_nice
    tools = [tool for tool in TOOL_KEYWORDS if re.search(rf"\b{re.escape(tool)}\b", lowered)]

    # --- Typed skill extraction ---
    typed = _extract_typed_skills(text)

    # --- Experience years ---
    years_min, years_max = _extract_years_range(text)
    # Back-compat: min_years_experience = the lowest explicit requirement
    min_years = years_min if years_min is not None else (years_max if years_max is not None else _extract_years(text))

    # --- Salary from text ---
    sal_min, sal_max, sal_period, sal_raw = _extract_salary_from_text(description or "")

    responsibilities = _extract_responsibilities(description or "")
    education = _extract_education(text)
    seniority = _extract_seniority(title, description or "")
    visa = _extract_visa(text)
    opt_allowed, stem_opt_allowed = _extract_opt(text)
    h1b_possible = _extract_h1b(text)
    us_citizens_only, security_clearance_required = _extract_citizenship_flags(text)
    role_family = infer_role_family(title, description or "")
    work_mode = normalize_work_mode(title, description or "")
    ai_relevance_score = _compute_ai_relevance(title, description or "")

    confidence = 0.2
    if must_have or typed["programming_languages"]:
        confidence += 0.3
    if nice_to_have or typed["frameworks"]:
        confidence += 0.1
    if tools or typed["cloud_tools"]:
        confidence += 0.1
    if min_years is not None:
        confidence += 0.2
    if education is not None:
        confidence += 0.1
    if responsibilities:
        confidence += 0.2

    parsed = {
        "must_have_skills": _normalize_list(must_have, limit=20),
        "nice_to_have_skills": _normalize_list(nice_to_have, limit=12),
        "tools_frameworks": _normalize_list(tools, limit=10),
        "responsibilities": responsibilities,
        "min_years_experience": min_years,
        # New typed fields
        "experience_years_min": years_min,
        "experience_years_max": years_max,
        "programming_languages": typed["programming_languages"],
        "frameworks": typed["frameworks"],
        "databases": typed["databases"],
        "cloud_tools": typed["cloud_tools"],
        "ml_ai_skills": typed["ml_ai_skills"],
        "certifications": typed["certifications"],
        "salary_text_raw": sal_raw,
        "salary_extracted_min": sal_min,
        "salary_extracted_max": sal_max,
        "salary_period": sal_period,
        # Existing fields
        "education_level": education,
        "seniority": seniority,
        "visa_sponsorship": visa,
        "opt_allowed": opt_allowed,
        "stem_opt_allowed": stem_opt_allowed,
        "h1b_possible": h1b_possible,
        "us_citizens_only": us_citizens_only,
        "security_clearance_required": security_clearance_required,
        "role_family": role_family,
        "work_mode": work_mode,
        "ai_relevance_score": ai_relevance_score,
        "confidence": round(min(confidence, 0.99), 3),
    }
    parsed["extraction_provenance"] = _build_extraction_provenance(title, description or "", parsed)
    return parsed


async def queue_job_requirements_analysis(db: AsyncSession, job: Job) -> None:
    """Upsert analysis state for a job so workers can process it in background."""

    if not settings.ENABLE_JOB_REQUIREMENTS_ANALYSIS:
        return

    content_hash = _content_hash(job.title or "", job.description or "")
    existing = (
        await db.execute(
            select(JobRequirement).where(
                JobRequirement.job_id == job.id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            JobRequirement(
                tenant_id=job.tenant_id,
                job_id=job.id,
                content_hash=content_hash,
                status="queued",
            )
        )
        return

    # Only requeue when content changed or previous run is incomplete.
    if existing.content_hash != content_hash or existing.status != "completed":
        existing.content_hash = content_hash
        existing.status = "queued"
        existing.last_error = None


async def recover_stale_requirement_jobs(db: AsyncSession) -> int:
    """Move stale in-flight jobs back to queued on startup."""

    stale_before = datetime.now(UTC) - timedelta(minutes=max(1, settings.JOB_REQUIREMENTS_STALE_MINUTES))
    result = await db.execute(
        update(JobRequirement)
        .where(
            JobRequirement.status == "processing",
            JobRequirement.updated_at < stale_before,
        )
        .values(status="queued", last_error="recovered_stale_processing")
    )
    return int(result.rowcount or 0)


async def queue_missing_job_requirements(db: AsyncSession, *, limit: int = 500) -> int:
    """Ensure jobs without analysis rows are queued for analysis."""

    subq = select(JobRequirement.job_id).where(JobRequirement.job_id == Job.id)
    rows = (
        await db.execute(
            select(Job)
            .where(
                Job.is_active.is_(True),
                ~exists(subq),
            )
            .order_by(Job.ingested_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    for job in rows:
        await queue_job_requirements_analysis(db, job)
    return len(rows)


async def _sync_requirements_to_typesense(job: Job, req: JobRequirement) -> None:
    client = get_typesense_client()
    await index_job(
        {
            "id": job.id,
            "tenant_id": job.tenant_id,
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "location_city": job.location_city,
            "location_state": job.location_state,
            "location_country": job.location_country,
            "remote": job.remote,
            "job_type": job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
            "experience_level": job.experience_level.value if hasattr(job.experience_level, "value") else str(job.experience_level),
            "category": job.category,
            "subcategory": job.subcategory,
            "work_mode": getattr(job, "work_mode", "unknown") or "unknown",
            "role_family": getattr(job, "role_family", "other") or "other",
            "tags": job.tags,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "sponsorship_score": job.sponsorship_score,
            "sponsorship_status": job.sponsorship_status,
            "sponsorship_confidence": job.sponsorship_confidence,
            "posted_at": job.posted_at,
            "source": job.source,
            "raw_json": job.raw_json,
            "is_active": job.is_active,
            "req_must_have_skills": req.must_have_skills,
            "req_nice_to_have_skills": req.nice_to_have_skills,
            "req_tools": req.tools_frameworks,
            "req_min_years": req.min_years_experience,
            "req_education": req.education_level or "",
            "req_seniority": req.seniority,
            "req_visa_sponsorship": req.visa_sponsorship,
            "req_confidence": req.confidence,
            "req_opt_allowed": getattr(req, "opt_allowed", "unknown") or "unknown",
            "req_h1b_possible": getattr(req, "h1b_possible", "unknown") or "unknown",
            "req_us_citizens_only": bool(getattr(req, "us_citizens_only", False)),
            "req_security_clearance": bool(getattr(req, "security_clearance_required", False)),
            "req_ai_relevance_score": float(getattr(req, "ai_relevance_score", 0.0) or 0.0),
            # New typed fields
            "req_programming_languages": getattr(req, "programming_languages", None) or [],
            "req_frameworks": getattr(req, "frameworks", None) or [],
            "req_databases": getattr(req, "databases", None) or [],
            "req_cloud_tools": getattr(req, "cloud_tools", None) or [],
            "req_ml_ai_skills": getattr(req, "ml_ai_skills", None) or [],
            "req_certifications": getattr(req, "certifications", None) or [],
            "req_experience_years_min": getattr(req, "experience_years_min", None),
            "req_experience_years_max": getattr(req, "experience_years_max", None),
            "req_salary_period": getattr(req, "salary_period", None) or "unknown",
            "req_ghost_risk_score": float(getattr(req, "ghost_risk_score", 0.0) or 0.0),
        },
        client,
    )


async def process_job_requirements_batch(*, count: int | None = None) -> dict[str, int]:
    """Process queued/failed requirement jobs and store parsed output."""

    batch_size = int(count or settings.JOB_REQUIREMENTS_BATCH_SIZE)
    processed = 0
    failed = 0
    recovered = 0
    queued_missing = 0

    async with AsyncSessionFactory() as db:
        recovered = await recover_stale_requirement_jobs(db)
        queued_missing = await queue_missing_job_requirements(db, limit=batch_size)
        await db.commit()

    for _ in range(batch_size):
        async with AsyncSessionFactory() as db:
            row = (
                await db.execute(
                    select(JobRequirement)
                    .where(
                        or_(
                            JobRequirement.status == "queued",
                            and_(
                                JobRequirement.status == "failed",
                                JobRequirement.attempt_count < int(settings.JOB_REQUIREMENTS_MAX_ATTEMPTS),
                            ),
                        )
                    )
                    .order_by(JobRequirement.updated_at.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if row is None:
                break

            row.status = "processing"
            row.attempt_count = int(row.attempt_count or 0) + 1
            await db.commit()

            job = (await db.execute(select(Job).where(Job.id == row.job_id))).scalar_one_or_none()
            if job is None:
                row.status = "failed"
                row.last_error = "job_not_found"
                await db.commit()
                failed += 1
                continue

            try:
                parsed = analyze_job_requirements(job.title or "", job.description or "")
                row.must_have_skills = parsed["must_have_skills"]
                row.nice_to_have_skills = parsed["nice_to_have_skills"]
                row.tools_frameworks = parsed["tools_frameworks"]
                row.responsibilities = parsed["responsibilities"]
                row.min_years_experience = parsed["min_years_experience"]
                row.education_level = parsed["education_level"]
                row.seniority = parsed["seniority"]
                row.visa_sponsorship = parsed["visa_sponsorship"]
                row.opt_allowed = parsed["opt_allowed"]
                row.stem_opt_allowed = parsed["stem_opt_allowed"]
                row.h1b_possible = parsed["h1b_possible"]
                row.us_citizens_only = parsed["us_citizens_only"]
                row.security_clearance_required = parsed["security_clearance_required"]
                row.role_family = parsed["role_family"]
                row.ai_relevance_score = parsed["ai_relevance_score"]
                row.confidence = parsed["confidence"]
                # New typed skill + salary fields (guarded for schema rollout)
                if hasattr(row, "experience_years_min"):
                    row.experience_years_min = parsed.get("experience_years_min")
                if hasattr(row, "experience_years_max"):
                    row.experience_years_max = parsed.get("experience_years_max")
                if hasattr(row, "programming_languages"):
                    row.programming_languages = parsed.get("programming_languages") or []
                if hasattr(row, "frameworks"):
                    row.frameworks = parsed.get("frameworks") or []
                if hasattr(row, "databases"):
                    row.databases = parsed.get("databases") or []
                if hasattr(row, "cloud_tools"):
                    row.cloud_tools = parsed.get("cloud_tools") or []
                if hasattr(row, "ml_ai_skills"):
                    row.ml_ai_skills = parsed.get("ml_ai_skills") or []
                if hasattr(row, "certifications"):
                    row.certifications = parsed.get("certifications") or []
                if hasattr(row, "salary_text_raw"):
                    row.salary_text_raw = parsed.get("salary_text_raw") or ""
                if hasattr(row, "salary_extracted_min"):
                    row.salary_extracted_min = parsed.get("salary_extracted_min")
                if hasattr(row, "salary_extracted_max"):
                    row.salary_extracted_max = parsed.get("salary_extracted_max")
                if hasattr(row, "salary_period"):
                    row.salary_period = parsed.get("salary_period") or "unknown"
                if hasattr(row, "extraction_provenance"):
                    row.extraction_provenance = parsed.get("extraction_provenance") or {}
                if hasattr(row, "ghost_risk_score"):
                    row.ghost_risk_score = _compute_ghost_risk(job, parsed)
                row.status = "completed"
                row.last_error = None
                row.analyzed_at = datetime.now(UTC)
                await _sync_requirements_to_typesense(job, row)
                await db.commit()
                processed += 1
            except Exception as exc:
                row.status = "failed"
                row.last_error = str(exc)[:500]
                await db.commit()
                failed += 1

    return {"processed": processed, "failed": failed, "recovered": recovered, "queued_missing": queued_missing}
