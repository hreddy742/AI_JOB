"""FastAPI application entrypoint."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.responses import JSONResponse
from structlog.contextvars import bind_contextvars, clear_contextvars

from core.config import settings
from core.logging import configure_logging
from core.middleware import RequestContextMiddleware
from browser_agent_v1.api.router import router as browser_agent_v1_router
from routers.admin import router as admin_router
from routers.ai import router as ai_router
from routers.alerts import router as alerts_router
from routers.analytics import router as analytics_router
from routers.auth import router as auth_router
from routers.applications import router as applications_router
from routers.copilot import router as copilot_router
from routers.h1b import router as h1b_router
from routers.health import router as health_router
from routers.jobs import router as jobs_router
from routers.opt import router as opt_router
from routers.outreach import router as outreach_router
from routers.profile import router as profile_router
from routers.referrals import router as referrals_router
from routers.resumes import router as resumes_router
from db.session import AsyncSessionFactory
from services.ingestion_service import periodic_ingestion_loop
from services.search_service import ensure_jobs_collection, get_typesense_client

configure_logging(settings.ENVIRONMENT)
logger = logging.getLogger(__name__)

if settings.GLITCHTIP_DSN:
    sentry_sdk.init(
        dsn=settings.GLITCHTIP_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.05,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
    )


def _validate_config() -> None:
    """Fail fast at startup if required settings are missing or invalid."""

    errors: list[str] = []
    secret_key_value = (settings.SECRET_KEY or "").strip().lower()
    secret_placeholders = {"change_me", "change-me", "dev-secret"}
    if not settings.SECRET_KEY:
        errors.append("SECRET_KEY must be set to a strong random value")
    elif settings.ENVIRONMENT == "production" and secret_key_value in secret_placeholders:
        errors.append("SECRET_KEY must be set to a strong random value")
    jwt_key_value = (settings.JWT_SECRET_KEY or "").strip().lower()
    jwt_placeholders = {
        "replace_with_128_char_hex_string",
        "change_me",
        "change-me",
        "dev-secret",
    }
    if not settings.JWT_SECRET_KEY:
        errors.append("JWT_SECRET_KEY must be set")
    elif settings.ENVIRONMENT == "production" and jwt_key_value in jwt_placeholders:
        errors.append("JWT_SECRET_KEY must be set to a strong random value")
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL must be set")
    if not settings.REDIS_URL:
        errors.append("REDIS_URL must be set")
    if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        errors.append("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set")
    if settings.COOKIE_SECURE is False and settings.ENVIRONMENT == "production":
        errors.append("COOKIE_SECURE must be True in production")
    if errors:
        raise RuntimeError(
            "Configuration errors (fix before starting):\n" + "\n".join(f"  - {e}" for e in errors)
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize external indices and shared resources at startup."""

    _validate_config()
    typesense_client = get_typesense_client()
    await ensure_jobs_collection(typesense_client)
    stop_event = asyncio.Event()
    app.state.ingestion_stop_event = stop_event

    app.state.ingestion_task = None
    if settings.ENABLE_BACKGROUND_INGESTION:
        app.state.ingestion_task = asyncio.create_task(
            periodic_ingestion_loop(AsyncSessionFactory, stop_event, interval_seconds=settings.INGESTION_INTERVAL_SECONDS)
        )
    yield
    stop_event.set()
    task = app.state.ingestion_task
    if task is not None:
        await task


app = FastAPI(title="APEX APPLY API", version="0.1.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

app.add_middleware(RequestContextMiddleware)
CSRF_COOKIE_NAME = "apex_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Build allowed origins from settings; allow localhost variants for dev.
_allowed_origins: list[str] = [
    origin.strip()
    for origin in [settings.FRONTEND_URL, *settings.CORS_ALLOWED_ORIGINS.split(",")]
    if origin and origin.strip()
]
if settings.ENVIRONMENT == "development":
    _allowed_origins += [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept", CSRF_HEADER_NAME],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add defensive security headers to every response."""

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=()",
    )
    if settings.ENVIRONMENT == "production":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )
    return response


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if csrf_cookie:
            csrf_header = request.headers.get(CSRF_HEADER_NAME, "")
            if not csrf_header or csrf_header != csrf_cookie:
                return JSONResponse(status_code=403, content={"detail": "Missing or invalid CSRF token"})
    return await call_next(request)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Bind request correlation metadata for structured logging."""

    clear_contextvars()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    bind_contextvars(request_id=request_id, path=request.url.path)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(resumes_router)
app.include_router(opt_router)
app.include_router(alerts_router)
app.include_router(h1b_router)
app.include_router(ai_router)
app.include_router(copilot_router)
app.include_router(referrals_router)
app.include_router(applications_router)
app.include_router(outreach_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(health_router)
if settings.ENABLE_BROWSER_AGENT_V1:
    app.include_router(browser_agent_v1_router)
