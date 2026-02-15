from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from bson import ObjectId
from shared.db import get_db, close_client
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, check_playwright_mcp, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME, CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes
from pydantic import BaseModel, Field
from typing import Optional, Literal
import os
import httpx
import asyncio
import logging
from pathlib import Path
import re

logger = get_logger(__name__)


def _fwd_headers(request: Request) -> dict:
    """Extract Authorization header for service-to-service forwarding."""
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}

# Constants
VIDEOS_DIR = "/videos"  # Must match playwright-mcp mount point
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")
EXECUTIONS_SERVICE_URL = os.getenv("EXECUTIONS_SERVICE_URL", "http://executions:8000")


def _strip_markdown_code_fences(text: str) -> str:
    s = (text or "").strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _normalize_script_for_playwright_mcp(script: str) -> str:
    """Normalize scripts for the Playwright MCP agent (/execute).

    The agent wraps the provided script inside `async (page) => { ... }`.
    So the stored script should be plain statements that use `page`.
    """

    text = _strip_markdown_code_fences(script or "").strip()
    if not text:
        return ""

    for _ in range(0, 3):
        m = re.search(
            r"async\s*function\s*\(\s*page\s*,\s*context\s*,\s*browser\s*\)\s*\{([\s\S]*?)\}\s*\)\s*\(\s*page\s*,\s*context\s*,\s*browser\s*\)",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        m = re.search(
            r"async\s*\(\s*page\s*\)\s*=>\s*\{([\s\S]*?)\}\s*\)\s*\(\s*page\s*\)",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        break

    # Prevent ReferenceError for legacy scripts.
    if re.search(r"\bcontext\b|\bbrowser\b", text):
        text = "const context = undefined;\nconst browser = undefined;\n" + text

    return text.strip()

# Video retention configuration
VIDEO_RETENTION_DAYS = int(os.getenv("VIDEO_RETENTION_DAYS", "30"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))

async def cleanup_old_videos():
    """Background task to delete videos older than VIDEO_RETENTION_DAYS"""
    while True:
        try:
            videos_path = Path(VIDEOS_DIR)
            if not videos_path.exists():
                await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)
                continue
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=VIDEO_RETENTION_DAYS)
            deleted_count = 0
            
            for video_file in videos_path.glob("*.webm"):
                try:
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(video_file.stat().st_mtime, tz=timezone.utc)
                    
                    if file_mtime < cutoff_time:
                        video_file.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old video: {video_file.name} (age: {(datetime.now(timezone.utc) - file_mtime).days} days)")
                except Exception as e:
                    logger.error(f"Error deleting video {video_file.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Video cleanup completed: {deleted_count} video(s) deleted")
            else:
                logger.info("Video cleanup completed: No old videos to delete")
                
        except Exception as e:
            logger.error(f"Error in video cleanup task: {e}")
        
        # Sleep until next cleanup interval
        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    setup_logging("automations", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    validate_settings()
    await ensure_indexes(get_db(), ["automations"])
    # Startup: Create cleanup task
    cleanup_task = asyncio.create_task(cleanup_old_videos())
    logger.info(f"Automations service ready (video retention: {VIDEO_RETENTION_DAYS}d, cleanup interval: {CLEANUP_INTERVAL_HOURS}h)")
    
    yield
    
    # Shutdown: Cancel cleanup task and close DB
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_client()
    logger.info("Automations service stopped")

app = FastAPI(
    title="Test Automation Service",
    version="1.0.0",
    description="""Service for managing and executing browser automation scripts.
    
    ## Features
    - Store automation scripts (Playwright/JavaScript)
    - Execute automations with video recording
    - Track generation type (static, execution-based)
    - Integrate with Playwright MCP for execution
    - Automatic video retention policy (30 days)
    
    ## Use Cases
    - Store automation scripts for test cases
    - Execute automated browser tests
    - Record test execution videos
    - Generate scripts from manual executions
    - Track automation status and history
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "automations", "description": "Operations on automation scripts"},
        {"name": "execution", "description": "Execute automations and manage results"},
        {"name": "videos", "description": "Video recording management"},
        {"name": "health", "description": "Service health and status"}
    ]
)

# Setup standardized error handlers
setup_all_error_handlers(app)

# Production middleware: auth, rate limiting, CORS
setup_auth(app)
setup_rate_limiting(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COL = "automations"
os.makedirs(VIDEOS_DIR, exist_ok=True)

AutomationStatus = Literal["not_started", "in_progress", "passing", "failing", "blocked"]
AutomationFramework = Literal["playwright", "selenium", "cypress", "pytest", "other"]

class AutomationCreate(BaseModel):
    test_case_id: str = Field(..., max_length=50)
    title: str = Field(..., max_length=500)
    framework: AutomationFramework = "playwright"
    script: str = Field(..., max_length=200000)
    status: AutomationStatus = "not_started"
    notes: Optional[str] = Field(None, max_length=10000)
    video_path: Optional[str] = Field(None, max_length=500)
    last_actions: Optional[str] = Field(None, max_length=100000)
    metadata: dict = {}

class AutomationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    framework: Optional[AutomationFramework] = None
    script: Optional[str] = Field(None, max_length=200000)
    status: Optional[AutomationStatus] = None
    notes: Optional[str] = Field(None, max_length=10000)
    last_run_result: Optional[str] = Field(None, max_length=10000)
    last_run_at: Optional[datetime] = None
    video_path: Optional[str] = Field(None, max_length=500)
    metadata: Optional[dict] = None

class AutomationOut(AutomationCreate):
    id: str
    last_run_result: Optional[str] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

def now():
    return datetime.now(timezone.utc)

def to_out(doc) -> AutomationOut:
    return AutomationOut(
        id=str(doc["_id"]),
        test_case_id=doc["test_case_id"],
        title=doc["title"],
        framework=doc["framework"],
        script=doc["script"],
        status=doc["status"],
        notes=doc.get("notes"),
        last_run_result=doc.get("last_run_result"),
        last_run_at=doc.get("last_run_at"),
        video_path=doc.get("video_path"),
        last_actions=doc.get("last_actions"),
        metadata=doc.get("metadata", {}),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

@app.get("/health")
async def health():
    # Check dependencies
    dependencies = {
        "mongodb": await check_mongodb(MONGO_URL, DB_NAME),
        "playwright_mcp": await check_playwright_mcp(PLAYWRIGHT_MCP_URL)
    }
    
    overall_status = aggregate_health_status(dependencies)
    
    return {
        "status": overall_status,
        "service": "automations",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_retention": {
            "retention_days": VIDEO_RETENTION_DAYS,
            "cleanup_interval_hours": CLEANUP_INTERVAL_HOURS,
            "videos_directory": VIDEOS_DIR
        },
        "dependencies": dependencies
    }

@app.post("/automations", response_model=AutomationOut, status_code=201)
async def create_automation(payload: AutomationCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)

@app.get("/automations", response_model=list[AutomationOut])
async def list_automations(
    test_case_id: str | None = Query(None),
    status: str | None = Query(None),
    framework: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if test_case_id:
        filt["test_case_id"] = test_case_id
    if status:
        filt["status"] = status
    if framework:
        filt["framework"] = framework
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]

@app.get("/automations/{automation_id}", response_model=AutomationOut)
async def get_automation(automation_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")
    return to_out(doc)

@app.put("/automations/{automation_id}", response_model=AutomationOut)
async def update_automation(automation_id: str, payload: AutomationUpdate):
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    patch["updated_at"] = now()
    res = await db[COL].update_one({"_id": oid(automation_id)}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Automation not found")
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    return to_out(doc)


@app.post("/automations/{automation_id}/normalize-script", response_model=AutomationOut)
async def normalize_automation_script(automation_id: str):
    """Normalize and persist the stored script so it runs under Playwright MCP /execute.

    This fixes legacy scripts that include markdown fences or wrappers referencing `context`/`browser`.
    """

    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")

    original = doc.get("script") or ""
    normalized = _normalize_script_for_playwright_mcp(original)
    if not normalized:
        raise HTTPException(status_code=400, detail="Script is empty or could not be normalized")

    patch = {
        "script": normalized,
        "updated_at": now(),
    }
    metadata = doc.get("metadata") or {}
    if isinstance(metadata, dict):
        metadata = {**metadata, "normalized_at": now().isoformat()}
        patch["metadata"] = metadata

    # Only write if it changed, but still return the current doc.
    if normalized != original:
        await db[COL].update_one({"_id": oid(automation_id)}, {"$set": patch})

    updated = await db[COL].find_one({"_id": oid(automation_id)})
    return to_out(updated)

@app.delete("/automations/{automation_id}", status_code=204)
async def delete_automation(automation_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(automation_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Automation not found")

@app.post("/automations/{automation_id}/execute")
async def execute_automation(automation_id: str, request: Request):
    """Execute automation via Playwright MCP and save video"""
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    # Update status to in_progress
    await db[COL].update_one(
        {"_id": oid(automation_id)},
        {"$set": {"status": "in_progress", "updated_at": now()}}
    )
    
    started_at = now()
    try:
        # Execute via Playwright MCP
        async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
            video_filename = f"{automation_id}_{int(now().timestamp())}.webm"
            video_path = os.path.join(VIDEOS_DIR, video_filename)
            
            # Call Playwright MCP to execute the script
            response = await client.post(
                f"{PLAYWRIGHT_MCP_URL}/execute",
                json={
                    "script": _normalize_script_for_playwright_mcp(doc.get("script") or ""),
                    "video_path": video_filename,  # Just filename, not full path
                    "record_video": True,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                status = "passing" if result.get("success") else "failing"

                duration_seconds = max(0, int((now() - started_at).total_seconds()))

                actions_taken = result.get("actions_taken")
                if actions_taken is None:
                    # Best-effort: store something useful for the UI.
                    actions_taken = result.get("error") or result.get("message") or None

                video_saved = bool(result.get("video_saved"))
                # If the agent reports a saved video, store the concrete path automations can serve.
                patch = {
                    "status": status,
                    "last_run_result": "passed" if result.get("success") else "failed",
                    "last_run_at": now(),
                    "updated_at": now(),
                }
                if actions_taken is not None:
                    patch["last_actions"] = actions_taken
                if video_saved:
                    patch["video_path"] = video_path

                # Create an execution record so runs show up as real pass/failed test executions.
                # Best-effort: do not fail the run if executions service is unavailable.
                execution_id = None
                try:
                    exec_payload = {
                        "test_case_id": doc.get("test_case_id"),
                        "execution_type": "automated",
                        "result": "passed" if result.get("success") else "failed",
                        "execution_date": now().isoformat(),
                        "duration_seconds": duration_seconds,
                        "metadata": {
                            "automation_id": automation_id,
                            "automation_title": doc.get("title"),
                            "framework": doc.get("framework"),
                            "video_saved": video_saved,
                            "video_path": video_path if video_saved else None,
                        },
                    }
                    if actions_taken is not None:
                        exec_payload["metadata"]["actions_taken"] = actions_taken
                    if result.get("error"):
                        exec_payload["metadata"]["error"] = result.get("error")

                    exec_response = await client.post(f"{EXECUTIONS_SERVICE_URL}/executions", json=exec_payload)
                    if exec_response.status_code in (200, 201):
                        exec_json = exec_response.json()
                        execution_id = exec_json.get("id")
                except Exception as e:
                    logger.warning(f"Could not create execution record: {e}")

                if execution_id:
                    patch.setdefault("metadata", doc.get("metadata", {}) or {})
                    patch["metadata"] = {**(doc.get("metadata", {}) or {}), "last_execution_id": execution_id}
                
                # Update automation with results
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {
                        "$set": patch
                    }
                )
                
                return {
                    "automation_id": automation_id,
                    "status": status,
                    "result": result.get("success"),
                    "video_available": video_saved,
                    "actions_taken": actions_taken,
                    "execution_id": execution_id,
                    "message": result.get("message", "Execution completed")
                }
            else:
                # Execution failed
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {
                        "$set": {
                            "status": "failing",
                            "last_run_result": "failed",
                            "last_run_at": now(),
                            "updated_at": now(),
                        }
                    }
                )
                raise HTTPException(status_code=500, detail="Execution failed")
                
    except Exception as e:
        # Update status to failing on error
        await db[COL].update_one(
            {"_id": oid(automation_id)},
            {
                "$set": {
                    "status": "failing",
                    "last_run_result": "error",
                    "last_run_at": now(),
                    "updated_at": now(),
                }
            }
        )
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

@app.post("/automations/{automation_id}/execute-with-mcp")
async def execute_automation_with_mcp(automation_id: str):
    """Execute automation using MCP protocol - Ollama interacts with Playwright via MCP tools"""
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    # Update status to in_progress
    await db[COL].update_one(
        {"_id": oid(automation_id)},
        {"$set": {"status": "in_progress", "updated_at": now()}}
    )
    
    try:
        # Execute via Playwright MCP with test description
        async with httpx.AsyncClient(timeout=300) as client:
            video_filename = f"{automation_id}_{int(now().timestamp())}.webm"
            
            # Get test case details for context
            test_description = doc.get("title", "")
            notes = doc.get("notes", "")
            metadata = doc.get("metadata", {})
            preconditions = metadata.get("preconditions", "")
            
            # Build comprehensive test description
            full_description = f"{test_description}\n\nPreconditions: {preconditions}\n\nNotes: {notes}"
            
            # Call Playwright MCP execute-test endpoint (uses MCP protocol internally)
            response = await client.post(
                f"{PLAYWRIGHT_MCP_URL}/execute-test",
                json={
                    "test_description": full_description,
                    "steps": doc.get("script", ""),  # Original script as reference
                    "video_path": video_filename,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                status = "passing" if result.get("success") else "failing"
                
                # Update automation with results
                video_path = os.path.join(VIDEOS_DIR, video_filename)
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {
                        "$set": {
                            "status": status,
                            "last_run_result": "passed" if result.get("success") else "failed",
                            "last_run_at": now(),
                            "video_path": video_path,
                            "updated_at": now(),
                            "last_actions": result.get("actions_taken", ""),
                        }
                    }
                )
                
                return {
                    "automation_id": automation_id,
                    "status": status,
                    "result": result.get("success"),
                    "video_available": True,
                    "actions_taken": result.get("actions_taken", ""),
                    "message": "Execution completed using MCP protocol"
                }
            else:
                # Execution failed
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {
                        "$set": {
                            "status": "failing",
                            "last_run_result": "failed",
                            "last_run_at": now(),
                            "updated_at": now(),
                        }
                    }
                )
                raise HTTPException(status_code=500, detail="MCP execution failed")
                
    except Exception as e:
        # Update status to failing on error
        await db[COL].update_one(
            {"_id": oid(automation_id)},
            {
                "$set": {
                    "status": "failing",
                    "last_run_result": "error",
                    "last_run_at": now(),
                    "updated_at": now(),
                }
            }
        )
        raise HTTPException(status_code=500, detail=f"MCP execution error: {str(e)}")

@app.get("/automations/{automation_id}/video")
async def get_video(automation_id: str):
    """Get the video recording of the automation execution"""
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    video_path = doc.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(video_path, media_type="video/webm")


@app.get("/videos/{video_filename}")
async def get_video_by_filename(video_filename: str):
    """Serve a recorded video by filename.

    This supports previewing recordings before an automation is saved.
    """
    # Basic filename validation to avoid path traversal.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.webm", video_filename):
        raise HTTPException(status_code=400, detail="Invalid video filename")

    video_path = os.path.join(VIDEOS_DIR, video_filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(video_path, media_type="video/webm")
