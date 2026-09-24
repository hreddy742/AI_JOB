"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_STARTTLS: bool = False
    SMTP_USE_TLS: bool = False
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Apex Apply"
    SMTP_FROM_EMAIL: str = "no-reply@apexapply.local"

    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 300
    RATE_LIMIT_REGISTER_MAX: int = 3
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = 3600
    RATE_LIMIT_RESET_MAX: int = 3
    RATE_LIMIT_RESET_WINDOW_SECONDS: int = 3600

    MAX_FAILED_LOGINS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    FRONTEND_URL: str = "http://localhost:3000"

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    WRITER_MODEL: str = "mistral:7b-instruct"
    REVIEWER_MODEL: str = "mistral:7b-instruct"
    KNOWLEDGE_MODEL: str = "qwen2:1.5b"
    COPILOT_MODEL: str = "llama3:8b"
    REFERRAL_MODEL: str = "qwen2:1.5b"

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

    TYPESENSE_HOST: str = "typesense"
    TYPESENSE_PORT: int = 8108
    TYPESENSE_API_KEY: str = "apex-apply-local-key"
    TYPESENSE_JOBS_COLLECTION: str = "jobs"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "apex-apply"

    ADZUNA_APP_ID: str = ""
    ADZUNA_API_KEY: str = ""
    USAJOBS_API_KEY: str = ""
    THE_MUSE_API_KEY: str = ""

    TAILORING_REVIEWER_THRESHOLD: float = 70.0
    TAILORING_MAX_RETRIES: int = 3
    OUTREACH_MAX_PER_DAY: int = 10
    COPILOT_MAX_HISTORY_MESSAGES: int = 20
    REFERRAL_MAX_PER_JOB: int = 5

    REFRESH_INTERVAL_GREENHOUSE: int = 300
    REFRESH_INTERVAL_LEVER: int = 300
    REFRESH_INTERVAL_REMOTEOK: int = 600
    REFRESH_INTERVAL_ADZUNA: int = 1800
    REFRESH_INTERVAL_ARBEITNOW: int = 1800
    REFRESH_INTERVAL_THE_MUSE: int = 3600
    REFRESH_INTERVAL_USAJOBS: int = 3600

    ENABLE_BACKGROUND_INGESTION: bool = False
    INGESTION_INTERVAL_SECONDS: int = 900
    ENABLE_JOB_EMBEDDINGS: bool = False
    JOB_RETENTION_DAYS: int = 3650

    GREENHOUSE_BOARD_TOKENS: str = ""
    LEVER_COMPANIES: str = ""
    JOBSPY_SITE_NAMES: str = ""

    ENVIRONMENT: str = "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()


settings: Settings = get_settings()
