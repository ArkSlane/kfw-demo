from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from pydantic import BaseModel, Field
from shared.db import get_db

router = APIRouter(prefix="/executions", tags=["executions"])

COL = "executions"

ResultType = Literal["passed", "failed", "blocked", "skipped"]


class ExecutionCreate(BaseModel):
    test_case_id: str = Field(..., max_length=50)
    release_id: Optional[str] = Field(None, max_length=50)
    execution_type: Literal["manual", "automated"] = "manual"
    result: ResultType
    execution_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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


def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now():
    return datetime.now(timezone.utc)


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


@router.post("", response_model=ExecutionOut, status_code=201)
async def create_execution(payload: ExecutionCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)


@router.get("", response_model=list[ExecutionOut])
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


@router.get("/{execution_id}", response_model=ExecutionOut)
async def get_execution(execution_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(execution_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution not found")
    return to_out(doc)


@router.put("/{execution_id}", response_model=ExecutionOut)
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
