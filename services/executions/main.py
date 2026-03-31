from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from shared.db import get_db, close_client
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME, CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("executions", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    validate_settings()
    await ensure_indexes(get_db(), ["executions"])
    logger.info("Executions service ready")
    yield
    await close_client()
    logger.info("Executions service stopped")


app = FastAPI(
    lifespan=lifespan,
    title="Executions Service",
    version="1.0.0",
    description="""Service for tracking test execution history and results.
    
    ## Features
    - Record test execution attempts
    - Track execution status and results
    - Link executions to test cases and automations
    - Store execution metadata (duration, video path, etc.)
    
    ## Use Cases
    - Track manual test execution results
    - Monitor automated test runs
    - Generate execution reports
    - Analyze test stability and flakiness
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "executions", "description": "Operations on test executions"},
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

COL = "executions"

def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now():
    return datetime.now(timezone.utc)

# Models (inline for simplicity)
from pydantic import BaseModel, Field
from typing import Optional, Literal

ResultType = Literal["passed", "failed", "blocked", "skipped"]

class ExecutionCreate(BaseModel):
    test_case_id: str = Field(..., max_length=50)
    release_id: Optional[str] = Field(None, max_length=50)
    execution_type: Literal["manual", "automated"] = "manual"
    result: ResultType
    execution_date: datetime = Field(default_factory=now)
    executed_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=10000)
    duration_seconds: Optional[int] = Field(None, ge=0, le=86400)
    metadata: dict = {}

class ExecutionUpdate(BaseModel):
    result: Optional[ResultType] = None
    execution_date: Optional[datetime] = None
    executed_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=10000)
    duration_seconds: Optional[int] = Field(None, ge=0, le=86400)
    metadata: Optional[dict] = None

class ExecutionOut(ExecutionCreate):
    id: str
    created_at: datetime
    updated_at: datetime


def to_out(doc) -> ExecutionOut:
    return ExecutionOut(
        id=str(doc["_id"]),
        test_case_id=doc["test_case_id"],
        release_id=doc.get("release_id"),
        execution_type=doc.get("execution_type", "manual"),
        result=doc["result"],
        execution_date=doc.get("execution_date", now()),
        executed_by=doc.get("executed_by"),
        notes=doc.get("notes"),
        duration_seconds=doc.get("duration_seconds"),
        metadata=doc.get("metadata", {}),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

@app.get("/health")
async def health():
    # Check dependencies
    dependencies = {
        "mongodb": await check_mongodb(MONGO_URL, DB_NAME)
    }
    
    overall_status = aggregate_health_status(dependencies)
    
    return {
        "status": overall_status,
        "service": "executions",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies
    }

@app.post("/executions", response_model=ExecutionOut, status_code=201)
async def create_execution(payload: ExecutionCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)

@app.get("/executions", response_model=list[ExecutionOut])
async def list_executions(
    test_case_id: Optional[str] = Query(None),
    release_id: Optional[str] = Query(None),
    result: Optional[ResultType] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if test_case_id:
        filt["test_case_id"] = test_case_id
    if release_id:
        filt["release_id"] = release_id
    if result:
        filt["result"] = result
    cursor = db[COL].find(filt).sort("execution_date", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]

@app.get("/executions/{execution_id}", response_model=ExecutionOut)
async def get_execution(execution_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(execution_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")
    return to_out(doc)

@app.put("/executions/{execution_id}", response_model=ExecutionOut)
async def update_execution(execution_id: str, payload: ExecutionUpdate):
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    patch["updated_at"] = now()
    res = await db[COL].update_one({"_id": oid(execution_id)}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Execution not found")
    doc = await db[COL].find_one({"_id": oid(execution_id)})
    return to_out(doc)
