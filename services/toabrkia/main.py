from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

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
    class Toab(BaseModel):
        prefix: str = Field(default="", description="Prefix")
        component_name: str = Field(default="", description="Component name")
        description: str = Field(default="", description="Description")

    class Rk(BaseModel):
        internal_effects: Literal["low", "medium", "high"] = Field(default="low")
        external_effects: Literal["low", "medium", "high"] = Field(default="low")
        availability: Literal["99.9%", "99%", "best_effort"] = Field(default="best_effort")
        complexity: Literal["simple", "moderate", "complex"] = Field(default="simple")

    class Ia(BaseModel):
        code_change: bool = Field(default=False)
        automated_test_intensity: Literal["none", "low", "medium", "high"] = Field(default="none")
        manual_test_intensity: Literal["none", "low", "medium", "high"] = Field(default="none")
        comments: str = Field(default="")

    toab: Toab | str = Field(default_factory=Toab, description="Test Objekt Abgrenzung")
    rk: Rk | str = Field(default_factory=Rk, description="Risiko Klassifizierung")
    ia: Ia | str = Field(default_factory=Ia, description="Impact Analyse")


class AssessmentOut(BaseModel):
    id: str
    release_id: str
    toab: AssessmentUpsert.Toab
    rk: AssessmentUpsert.Rk
    ia: AssessmentUpsert.Ia
    created_at: datetime
    updated_at: datetime


def _normalize_toab(value: Any) -> AssessmentUpsert.Toab:
    if isinstance(value, AssessmentUpsert.Toab):
        return value
    if isinstance(value, str):
        return AssessmentUpsert.Toab(description=value)
    if isinstance(value, dict):
        return AssessmentUpsert.Toab.model_validate(value)
    return AssessmentUpsert.Toab()


def _normalize_rk(value: Any) -> AssessmentUpsert.Rk:
    if isinstance(value, AssessmentUpsert.Rk):
        return value
    if isinstance(value, str):
        # Legacy free-text stored; keep as best-effort comment in the new structured model
        return AssessmentUpsert.Rk()
    if isinstance(value, dict):
        return AssessmentUpsert.Rk.model_validate(value)
    return AssessmentUpsert.Rk()


def _normalize_ia(value: Any) -> AssessmentUpsert.Ia:
    if isinstance(value, AssessmentUpsert.Ia):
        return value
    if isinstance(value, str):
        return AssessmentUpsert.Ia(comments=value)
    if isinstance(value, dict):
        return AssessmentUpsert.Ia.model_validate(value)
    return AssessmentUpsert.Ia()


def to_out(doc) -> AssessmentOut:
    return AssessmentOut(
        id=str(doc["_id"]),
        release_id=doc["release_id"],
        toab=_normalize_toab(doc.get("toab")),
        rk=_normalize_rk(doc.get("rk")),
        ia=_normalize_ia(doc.get("ia")),
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

    toab = _normalize_toab(payload.toab)
    rk = _normalize_rk(payload.rk)
    ia = _normalize_ia(payload.ia)

    if not existing:
        doc = {
            "release_id": release_id,
            "toab": toab.model_dump(),
            "rk": rk.model_dump(),
            "ia": ia.model_dump(),
            "created_at": ts,
            "updated_at": ts,
        }
        res = await db[COL].insert_one(doc)
        created = await db[COL].find_one({"_id": res.inserted_id})
        return to_out(created)

    patch = {
        "toab": toab.model_dump(),
        "rk": rk.model_dump(),
        "ia": ia.model_dump(),
        "updated_at": ts,
    }

    await db[COL].update_one({"_id": existing["_id"]}, {"$set": patch})
    updated = await db[COL].find_one({"_id": existing["_id"]})
    return to_out(updated)


@app.delete(
    "/assessments/{assessment_id}",
    tags=["assessments"],
)
async def delete_assessment(assessment_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(assessment_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"status": "deleted"}
