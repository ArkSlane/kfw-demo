import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.db import get_db, close_client
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, check_playwright_mcp, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME, CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes

from routers import requirements, testcases, releases, executions, automations, assessments

logger = get_logger(__name__)

VIDEOS_DIR = "/videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)

PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("core", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    validate_settings()
    db = get_db()
    await ensure_indexes(db, ["requirements", "testcases", "releases", "executions", "automations", "release_assessments"])
    # Start video cleanup background task
    cleanup_task = asyncio.create_task(automations.cleanup_old_videos())
    logger.info("Core service ready")
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_client()
    logger.info("Core service stopped")


app = FastAPI(
    lifespan=lifespan,
    title="Core API Service",
    version="1.0.0",
    description="Unified service for requirements, testcases, releases, executions, automations, and release assessments.",
    docs_url="/docs",
    redoc_url="/redoc",
)

setup_all_error_handlers(app)
setup_auth(app)
setup_rate_limiting(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(requirements.router)
app.include_router(testcases.router)
app.include_router(releases.router)
app.include_router(executions.router)
app.include_router(automations.router)
app.include_router(assessments.router)


@app.get("/health")
async def health():
    dependencies = {
        "mongodb": await check_mongodb(MONGO_URL, DB_NAME),
        "playwright_mcp": await check_playwright_mcp(PLAYWRIGHT_MCP_URL),
    }
    overall_status = aggregate_health_status(dependencies)
    return {
        "status": overall_status,
        "service": "core",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies,
    }
