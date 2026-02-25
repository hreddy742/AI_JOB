"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging
from core.middleware import RequestContextMiddleware
from routers.admin import router as admin_router
from routers.analytics import router as analytics_router
from routers.auth import router as auth_router
from routers.applications import router as applications_router
from routers.copilot import router as copilot_router
from routers.jobs import router as jobs_router
from routers.outreach import router as outreach_router
from routers.profile import router as profile_router
from routers.referrals import router as referrals_router
from routers.resumes import router as resumes_router
from db.session import AsyncSessionFactory
from services.ingestion_service import periodic_ingestion_loop
from services.search_service import ensure_jobs_collection, get_typesense_client

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize external indices and shared resources at startup."""

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

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(resumes_router)
app.include_router(copilot_router)
app.include_router(referrals_router)
app.include_router(applications_router)
app.include_router(outreach_router)
app.include_router(analytics_router)
app.include_router(admin_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Basic health endpoint."""

    return {"status": "ok"}
