from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from shared.db import get_db
from shared.models import TestcaseCreate, TestcaseUpdate, TestcaseOut
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME

app = FastAPI(
    title="Testcase Management Service",
    version="1.0.0",
    description="""CRUD service for managing Gherkin/Cucumber test cases linked to requirements.
    
    ## Features
    - Create, read, update, and delete test cases
    - Store test cases in Gherkin format
    - Link test cases to requirements
    - Track test case status (draft, ready, passed, failed, approved, inactive)
    - Version control for test cases
    - Metadata and tagging system
    
    ## Use Cases
    - Store manual and automated test cases
    - Generate automation scripts from test cases
    - Track test case execution history
    - Organize tests by requirement
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "testcases", "description": "Operations on test cases"},
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

COL = "testcases"

def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

def now():
    return datetime.now(timezone.utc)

def to_out(doc) -> TestcaseOut:
    return TestcaseOut(
        id=str(doc["_id"]),
        requirement_id=doc["requirement_id"],
        title=doc["title"],
        gherkin=doc["gherkin"],
        status=doc["status"],
        version=doc.get("version", 1),
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
        "service": "testcases",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies
    }

@app.post("/testcases", response_model=TestcaseOut, status_code=201)
async def create_testcase(payload: TestcaseCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)

@app.get("/testcases", response_model=list[TestcaseOut])
async def list_testcases(
    requirement_id: str | None = Query(None),
    status: str | None = Query(None, description="draft|approved|inactive"),
    q: str | None = Query(None, description="Search in title/gherkin"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if requirement_id:
        filt["requirement_id"] = requirement_id
    if status:
        filt["status"] = status
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"gherkin": {"$regex": q, "$options": "i"}}]
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]

@app.get("/testcases/{testcase_id}", response_model=TestcaseOut)
async def get_testcase(testcase_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(testcase_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return to_out(doc)

@app.put("/testcases/{testcase_id}", response_model=TestcaseOut)
async def update_testcase(testcase_id: str, payload: TestcaseUpdate):
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    patch["updated_at"] = now()
    res = await db[COL].update_one({"_id": oid(testcase_id)}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Testcase not found")
    doc = await db[COL].find_one({"_id": oid(testcase_id)})
    return to_out(doc)

@app.delete("/testcases/{testcase_id}", status_code=204)
async def delete_testcase(testcase_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(testcase_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return None
