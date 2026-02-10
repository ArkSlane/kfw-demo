from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from shared.db import get_db
from shared.models import ReleaseCreate, ReleaseUpdate, ReleaseOut
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME

app = FastAPI(
    title="Releases Management Service",
    version="1.0.0",
    description="""Service for managing releases and organizing requirements/testcases by release.
    
    ## Features
    - Create, read, update, and delete releases
    - Link requirements and test cases to releases
    - Track release dates and timelines
    - Generate release reports
    
    ## Use Cases
    - Plan and track software releases
    - Group requirements by release version
    - Monitor test coverage per release
    - Generate release documentation
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "releases", "description": "Operations on releases"},
        {"name": "health", "description": "Service health and status"}
    ]
)

# Setup standardized error handlers
setup_all_error_handlers(app)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COL = "releases"

def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

def now():
    return datetime.now(timezone.utc)

def to_out(doc) -> ReleaseOut:
    return ReleaseOut(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description"),
        from_date=doc.get("from_date"),
        to_date=doc.get("to_date"),
        requirement_ids=doc.get("requirement_ids", []),
        testcase_ids=doc.get("testcase_ids", []),
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
        "service": "releases",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies
    }

@app.post("/releases", response_model=ReleaseOut, status_code=201)
async def create_release(payload: ReleaseCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)

@app.get("/releases", response_model=list[ReleaseOut])
async def list_releases(
    q: str | None = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if q:
        filt = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]}
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]

@app.get("/releases/{release_id}", response_model=ReleaseOut)
async def get_release(release_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(release_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Release not found")
    return to_out(doc)

@app.put("/releases/{release_id}", response_model=ReleaseOut)
async def update_release(release_id: str, payload: ReleaseUpdate):
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    patch["updated_at"] = now()
    res = await db[COL].update_one({"_id": oid(release_id)}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Release not found")
    doc = await db[COL].find_one({"_id": oid(release_id)})
    return to_out(doc)

@app.delete("/releases/{release_id}", status_code=204)
async def delete_release(release_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(release_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Release not found")
    return None
