"""Application configuration."""

from functools import lru_cache

from pydantic import model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET_VALUES = {
    "",
    "change-me",
    "dev-secret",
    "replace-with-glitchtip-secret",
    "replace-with-local-jwt-secret",
    "replace-with-local-secret",
}


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=(".env.example", ".env", ".env.local"), extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_blank_env_values(cls, values: object) -> object:
        """Treat blank env values as unset so typed defaults still apply."""

        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        for key, value in list(normalized.items()):
            if isinstance(value, str) and value.strip() == "":
                normalized.pop(key)
        return normalized

    # Core app / security
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str

    # JWT / session lifetime
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Cookie / browser session posture
    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # Email / notifications
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_STARTTLS: bool = False
    SMTP_USE_TLS: bool = False
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Apex Apply"
    SMTP_FROM_EMAIL: str = "no-reply@apexapply.local"

    # API abuse controls
    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 300
    RATE_LIMIT_REGISTER_MAX: int = 3
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = 3600
    RATE_LIMIT_RESET_MAX: int = 3
    RATE_LIMIT_RESET_WINDOW_SECONDS: int = 3600

    MAX_FAILED_LOGINS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Frontend routing
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ALLOWED_ORIGINS: str = ""

    # LLM / local AI stack
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    CREATIVE_LLM_MODEL: str = "llama3.1:8b"
    STRUCTURED_LLM_MODEL: str = "mistral:7b"
    WRITER_MODEL: str = "mistral:7b"
    REVIEWER_MODEL: str = "mistral:7b"
    KNOWLEDGE_MODEL: str = "mistral:7b"
    COPILOT_MODEL: str = "llama3:8b"
    REFERRAL_MODEL: str = "qwen2:1.5b"

    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024

    # Search
    TYPESENSE_HOST: str = "typesense"
    TYPESENSE_PORT: int = 8108
    TYPESENSE_API_KEY: str = "apex-apply-local-key"
    TYPESENSE_JOBS_COLLECTION: str = "jobs"

    # Object storage
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "apex-apply"

    # Source APIs / connectors
    ADZUNA_APP_ID: str = ""
    ADZUNA_API_KEY: str = ""
    JOOBLE_API_KEY: str = ""
    CAREERJET_API_KEY: str = ""
    USAJOBS_API_KEY: str = ""
    USAJOBS_USER_AGENT: str = ""
    THE_MUSE_API_KEY: str = ""
    RSS_FEED_URLS: str = ""
    HANDSHAKE_ENABLED: bool = False
    HANDSHAKE_EMAIL: str = ""
    HANDSHAKE_PASSWORD: str = ""

    # Product policy / workflow budgets
    TAILORING_REVIEWER_THRESHOLD: float = 70.0
    TAILORING_MAX_RETRIES: int = 3
    OUTREACH_MAX_PER_DAY: int = 10
    ALERT_BUDGET_PER_DAY: int = 10
    COPILOT_MAX_HISTORY_MESSAGES: int = 20
    COPILOT_RAW_TURNS_WINDOW: int = 30
    COPILOT_RAW_MESSAGES_CAP: int = 120
    COPILOT_INACTIVE_RETENTION_DAYS: int = 30
    APPLIED_APPLICATION_RETENTION_DAYS: int = 15
    REFERRAL_MAX_PER_JOB: int = 5

    # Source refresh cadence
    REFRESH_INTERVAL_GREENHOUSE: int = 300
    REFRESH_INTERVAL_LEVER: int = 300
    REFRESH_INTERVAL_REMOTEOK: int = 600
    REFRESH_INTERVAL_ADZUNA: int = 1800
    REFRESH_INTERVAL_ARBEITNOW: int = 1800
    REFRESH_INTERVAL_THE_MUSE: int = 3600
    REFRESH_INTERVAL_USAJOBS: int = 3600

    # Ingestion / ranking / search pipeline
    ENABLE_BACKGROUND_INGESTION: bool = True
    INGESTION_INTERVAL_SECONDS: int = 900
    INGESTION_GLOBAL_CONCURRENCY: int = 8
    INGESTION_PER_TENANT_CONCURRENCY: int = 1
    ENABLE_JOB_EMBEDDINGS: bool = True
    ENABLE_RERANKING: bool = False
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_MAX_CANDIDATES: int = 40
    RERANK_MIN_CANDIDATES: int = 5
    RERANK_TIMEOUT_MS: int = 1200
    JOB_RETENTION_DAYS: int = 90
    ENABLE_JOB_REQUIREMENTS_ANALYSIS: bool = True
    JOB_REQUIREMENTS_MAX_ATTEMPTS: int = 5
    JOB_REQUIREMENTS_BATCH_SIZE: int = 100
    JOB_REQUIREMENTS_STALE_MINUTES: int = 15
    GLOBAL_JOBS_CATALOG_ENABLED: bool = True
    ENABLE_JOB_DETAIL_ENRICHMENT: bool = True
    JOB_DETAIL_ENRICHMENT_BATCH_SIZE: int = 50
    JOB_DETAIL_MIN_DESCRIPTION_CHARS: int = 300

    # Browser Agent control plane
    # ENABLE_BROWSER_AGENT_V1 is the hard subsystem gate.
    # BROWSER_AGENT_V1_ENABLED is the rollout base flag used by tenant state logic.
    ENABLE_BROWSER_AGENT_V1: bool = True
    BROWSER_AGENT_V1_ENABLED: bool = True
    BROWSER_AGENT_V1_SHADOW_MODE: bool = False
    BROWSER_AGENT_V1_PERCENT_ROLLOUT: int = 0
    BROWSER_AGENT_V1_INTERNAL_ALLOWLIST: str = ""
    BROWSER_AGENT_V1_DISABLED_PROVIDERS: str = ""
    BROWSER_AGENT_V1_BROWSER_PRIMARY_ENABLED: bool = False
    BROWSER_AGENT_V1_PILOT_PROVIDERS: str = ""
    BROWSER_AGENT_V1_PILOT_TENANTS: str = ""
    BROWSER_AGENT_V1_PILOT_PERCENT_ROLLOUT: int = 0
    BROWSER_AGENT_V1_ARTIFACT_PREFIX: str = "browser-agent-v1"
    BROWSER_AGENT_V1_HEADLESS: bool = True
    BROWSER_AGENT_V1_MAX_STEPS_PER_RUN: int = 8
    BROWSER_AGENT_V1_STALE_RUN_MINUTES: int = 30
    BROWSER_AGENT_V1_UPLOAD_CONFIRMATION_TIMEOUT_MS: int = 4000
    BROWSER_AGENT_V1_RESUME_SECRET_TTL_SECONDS: int = 3600
    BROWSER_AGENT_V1_WORKER_METRICS_PORT: int = 9201
    BROWSER_AGENT_V1_MAINT_WORKER_METRICS_PORT: int = 9202
    BROWSER_AGENT_V1_REFRESH_ANALYTICS_MARTS: bool = True
    BROWSER_AGENT_V1_ANALYTICS_REFRESH_MINUTES: int = 15

    # Source-expansion / network / scraping controls
    GREENHOUSE_BOARD_TOKENS: str = ""
    LEVER_COMPANIES: str = ""
    ASHBY_COMPANIES: str = ""
    PROXY_URL: str | None = None
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"
    ENABLE_CONTINUOUS_USA_SCRAPER: bool = False
    STREAM_MAX_ATTEMPTS: int = 5
    JOB_COVERAGE_ENABLED: bool = True
    JOB_COVERAGE_SOURCE_CONCURRENCY: int = 4
    JOB_COVERAGE_TIER1_SOURCES: str = "greenhouse,lever,usajobs,arbeitnow,remoteok,adzuna,jooble"
    JOB_COVERAGE_DISCOVERY_CRON_MINUTES: int = 120

    # Environment / observability
    ENVIRONMENT: str = "development"
    APP_VERSION: str = "0.1.0"
    GLITCHTIP_DSN: str = ""
    GRAFANA_PASSWORD: str = "admin"

    @model_validator(mode="after")
    def validate_security_posture(self) -> "Settings":
        environment = (self.ENVIRONMENT or "development").strip().lower()
        strict_env = environment in {"production", "staging"}
        if not strict_env and not self.COOKIE_SECURE:
            self.COOKIE_SECURE = True
        if strict_env:
            if self.SECRET_KEY.strip() in PLACEHOLDER_SECRET_VALUES:
                raise ValueError("SECRET_KEY must be rotated and non-placeholder in production-like environments")
            if self.JWT_SECRET_KEY.strip() in PLACEHOLDER_SECRET_VALUES:
                raise ValueError("JWT_SECRET_KEY must be rotated and non-placeholder in production-like environments")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must remain enabled in production-like environments")
        if self.SMTP_STARTTLS and self.SMTP_USE_TLS:
            raise ValueError("SMTP_STARTTLS and SMTP_USE_TLS cannot both be enabled")
        return self

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()


settings: Settings = get_settings()
