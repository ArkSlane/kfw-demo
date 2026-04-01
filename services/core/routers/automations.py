from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from bson import ObjectId
from pydantic import BaseModel, Field
from shared.db import get_db
from shared.health import check_playwright_mcp
from shared.logging_config import get_logger
import os
import httpx
import asyncio
import re
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter(tags=["automations"])

COL = "automations"
EXEC_COL = "executions"

VIDEOS_DIR = "/videos"
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")

# Video retention configuration
VIDEO_RETENTION_DAYS = int(os.getenv("VIDEO_RETENTION_DAYS", "30"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))

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
    review_status: Optional[str] = None


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
    review_status: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class AutomationOut(AutomationCreate):
    id: str
    last_run_result: Optional[str] = None
    last_run_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now():
    return datetime.now(timezone.utc)


def _fwd_headers(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}


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

    if re.search(r"\bcontext\b|\bbrowser\b", text):
        text = "const context = undefined;\nconst browser = undefined;\n" + text

    return text.strip()


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
        review_status=doc.get("review_status"),
        reviewed_by=doc.get("reviewed_by"),
        reviewed_at=doc.get("reviewed_at"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


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
                    file_mtime = datetime.fromtimestamp(video_file.stat().st_mtime, tz=timezone.utc)
                    if file_mtime < cutoff_time:
                        video_file.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old video: {video_file.name}")
                except Exception as e:
                    logger.error(f"Error deleting video {video_file.name}: {e}")

            if deleted_count > 0:
                logger.info(f"Video cleanup: {deleted_count} video(s) deleted")
        except Exception as e:
            logger.error(f"Error in video cleanup task: {e}")

        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)


@router.post("/automations", response_model=AutomationOut, status_code=201)
async def create_automation(payload: AutomationCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)


@router.get("/automations", response_model=list[AutomationOut])
async def list_automations(
    test_case_id: str | None = Query(None),
    status: str | None = Query(None),
    framework: str | None = Query(None),
    review_status: str | None = Query(None),
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
    if review_status:
        filt["review_status"] = review_status
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]


@router.get("/automations/{automation_id}", response_model=AutomationOut)
async def get_automation(automation_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")
    return to_out(doc)


@router.put("/automations/{automation_id}", response_model=AutomationOut)
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


@router.post("/automations/{automation_id}/normalize-script", response_model=AutomationOut)
async def normalize_automation_script(automation_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")

    original = doc.get("script") or ""
    normalized = _normalize_script_for_playwright_mcp(original)
    if not normalized:
        raise HTTPException(status_code=400, detail="Script is empty or could not be normalized")

    patch = {"script": normalized, "updated_at": now()}
    metadata = doc.get("metadata") or {}
    if isinstance(metadata, dict):
        metadata = {**metadata, "normalized_at": now().isoformat()}
        patch["metadata"] = metadata

    if normalized != original:
        await db[COL].update_one({"_id": oid(automation_id)}, {"$set": patch})

    updated = await db[COL].find_one({"_id": oid(automation_id)})
    return to_out(updated)


@router.delete("/automations/{automation_id}", status_code=204)
async def delete_automation(automation_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(automation_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Automation not found")


@router.post("/automations/{automation_id}/approve", response_model=AutomationOut)
async def approve_automation(automation_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(automation_id)},
        {"$set": {"review_status": "approved", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Automation not found")
    return to_out(result)


@router.post("/automations/{automation_id}/reject", response_model=AutomationOut)
async def reject_automation(automation_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(automation_id)},
        {"$set": {"review_status": "rejected", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Automation not found")
    return to_out(result)


@router.post("/automations/{automation_id}/execute")
async def execute_automation(automation_id: str, request: Request):
    """Execute automation via Playwright MCP and save video"""
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")

    await db[COL].update_one(
        {"_id": oid(automation_id)},
        {"$set": {"status": "in_progress", "updated_at": now()}}
    )

    started_at = now()
    try:
        async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
            video_filename = f"{automation_id}_{int(now().timestamp())}.webm"
            video_path = os.path.join(VIDEOS_DIR, video_filename)

            response = await client.post(
                f"{PLAYWRIGHT_MCP_URL}/execute",
                json={
                    "script": _normalize_script_for_playwright_mcp(doc.get("script") or ""),
                    "video_path": video_filename,
                    "record_video": True,
                }
            )

            if response.status_code == 200:
                result = response.json()
                status = "passing" if result.get("success") else "failing"
                duration_seconds = max(0, int((now() - started_at).total_seconds()))

                actions_taken = result.get("actions_taken")
                if actions_taken is None:
                    actions_taken = result.get("error") or result.get("message") or None

                video_saved = bool(result.get("video_saved"))
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

                # Create execution record directly (same DB, no HTTP call needed)
                execution_id = None
                try:
                    ts = now()
                    exec_doc = {
                        "test_case_id": doc.get("test_case_id"),
                        "execution_type": "automated",
                        "result": "passed" if result.get("success") else "failed",
                        "execution_date": ts,
                        "duration_seconds": duration_seconds,
                        "metadata": {
                            "automation_id": automation_id,
                            "automation_title": doc.get("title"),
                            "framework": doc.get("framework"),
                            "video_saved": video_saved,
                            "video_path": video_path if video_saved else None,
                        },
                        "created_at": ts,
                        "updated_at": ts,
                    }
                    if actions_taken is not None:
                        exec_doc["metadata"]["actions_taken"] = actions_taken
                    if result.get("error"):
                        exec_doc["metadata"]["error"] = result.get("error")

                    exec_res = await db[EXEC_COL].insert_one(exec_doc)
                    execution_id = str(exec_res.inserted_id)
                except Exception as e:
                    logger.warning(f"Could not create execution record: {e}")

                if execution_id:
                    patch.setdefault("metadata", doc.get("metadata", {}) or {})
                    patch["metadata"] = {**(doc.get("metadata", {}) or {}), "last_execution_id": execution_id}

                await db[COL].update_one({"_id": oid(automation_id)}, {"$set": patch})

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
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {"$set": {"status": "failing", "last_run_result": "failed", "last_run_at": now(), "updated_at": now()}}
                )
                raise HTTPException(status_code=500, detail="Execution failed")

    except HTTPException:
        raise
    except Exception as e:
        await db[COL].update_one(
            {"_id": oid(automation_id)},
            {"$set": {"status": "failing", "last_run_result": "error", "last_run_at": now(), "updated_at": now()}}
        )
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.post("/automations/{automation_id}/execute-with-mcp")
async def execute_automation_with_mcp(automation_id: str):
    """Execute automation using MCP protocol"""
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")

    await db[COL].update_one(
        {"_id": oid(automation_id)},
        {"$set": {"status": "in_progress", "updated_at": now()}}
    )

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            video_filename = f"{automation_id}_{int(now().timestamp())}.webm"

            test_description = doc.get("title", "")
            notes = doc.get("notes", "")
            metadata = doc.get("metadata", {})
            preconditions = metadata.get("preconditions", "")

            full_description = f"{test_description}\n\nPreconditions: {preconditions}\n\nNotes: {notes}"

            response = await client.post(
                f"{PLAYWRIGHT_MCP_URL}/execute-test",
                json={
                    "test_description": full_description,
                    "steps": doc.get("script", ""),
                    "video_path": video_filename,
                }
            )

            if response.status_code == 200:
                result = response.json()
                status = "passing" if result.get("success") else "failing"

                video_path = os.path.join(VIDEOS_DIR, video_filename)
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {"$set": {
                        "status": status,
                        "last_run_result": "passed" if result.get("success") else "failed",
                        "last_run_at": now(),
                        "video_path": video_path,
                        "updated_at": now(),
                        "last_actions": result.get("actions_taken", ""),
                    }}
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
                await db[COL].update_one(
                    {"_id": oid(automation_id)},
                    {"$set": {"status": "failing", "last_run_result": "failed", "last_run_at": now(), "updated_at": now()}}
                )
                raise HTTPException(status_code=500, detail="MCP execution failed")

    except HTTPException:
        raise
    except Exception as e:
        await db[COL].update_one(
            {"_id": oid(automation_id)},
            {"$set": {"status": "failing", "last_run_result": "error", "last_run_at": now(), "updated_at": now()}}
        )
        raise HTTPException(status_code=500, detail=f"MCP execution error: {str(e)}")


@router.get("/automations/{automation_id}/video")
async def get_video(automation_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(automation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Automation not found")

    video_path = doc.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(video_path, media_type="video/webm")


@router.get("/videos/{video_filename}")
async def get_video_by_filename(video_filename: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.webm", video_filename):
        raise HTTPException(status_code=400, detail="Invalid video filename")

    video_path = os.path.join(VIDEOS_DIR, video_filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(video_path, media_type="video/webm")
