from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.db import get_db
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME


app = FastAPI(
    title="Release Assessments Service",
    version="1.0.0",
    description=(
        """Service for capturing TOAB/RK/IA (Test Objekt Abgrenzung, Risiko Klassifizierung, Impact Analyse)
        per release.

        ## Features
        - Store a TOAB/RK/IA assessment per release
        - Update existing assessments (upsert-by-release)
        - Query assessments by release
        """
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "assessments", "description": "TOAB/RK/IA assessments"},
        {"name": "health", "description": "Service health and status"},
    ],
)

setup_all_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COL = "release_assessments"


def now() -> datetime:
    return datetime.now(timezone.utc)


def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


class AssessmentUpsert(BaseModel):
    toab: str = Field(default="", description="Test Objekt Abgrenzung")
    rk: str = Field(default="", description="Risiko Klassifizierung")
    ia: str = Field(default="", description="Impact Analyse")


class AssessmentOut(BaseModel):
    id: str
    release_id: str
    toab: str
    rk: str
    ia: str
    created_at: datetime
    updated_at: datetime


def to_out(doc) -> AssessmentOut:
    return AssessmentOut(
        id=str(doc["_id"]),
        release_id=doc["release_id"],
        toab=doc.get("toab", ""),
        rk=doc.get("rk", ""),
        ia=doc.get("ia", ""),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@app.get("/health", tags=["health"])
async def health():
    dependencies = {"mongodb": await check_mongodb(MONGO_URL, DB_NAME)}
    overall_status = aggregate_health_status(dependencies)

    return {
        "status": overall_status,
        "service": "toabrkia",
        "timestamp": now().isoformat(),
        "dependencies": dependencies,
    }


@app.get("/assessments", response_model=list[AssessmentOut], tags=["assessments"])
async def list_assessments(
    release_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if release_id:
        filt["release_id"] = release_id

    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]


@app.get(
    "/assessments/by-release/{release_id}",
    response_model=AssessmentOut,
    tags=["assessments"],
)
async def get_assessment_by_release(release_id: str):
    db = get_db()
    doc = await db[COL].find_one({"release_id": release_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return to_out(doc)


@app.put(
    "/assessments/by-release/{release_id}",
    response_model=AssessmentOut,
    tags=["assessments"],
)
async def upsert_assessment_by_release(release_id: str, payload: AssessmentUpsert):
    db = get_db()
    existing = await db[COL].find_one({"release_id": release_id})
    ts = now()

    if not existing:
        doc = {
            "release_id": release_id,
            "toab": payload.toab,
            "rk": payload.rk,
            "ia": payload.ia,
            "created_at": ts,
            "updated_at": ts,
        }
        res = await db[COL].insert_one(doc)
        created = await db[COL].find_one({"_id": res.inserted_id})
        return to_out(created)

    patch = {
        "toab": payload.toab,
        "rk": payload.rk,
        "ia": payload.ia,
        "updated_at": ts,
    }

    await db[COL].update_one({"_id": existing["_id"]}, {"$set": patch})
    updated = await db[COL].find_one({"_id": existing["_id"]})
    return to_out(updated)
