from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from shared.db import get_db
from shared.models import TestcaseCreate, TestcaseUpdate, TestcaseOut

router = APIRouter(prefix="/testcases", tags=["testcases"])

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
        requirement_id=doc.get("requirement_id"),
        title=doc["title"],
        gherkin=doc["gherkin"],
        status=doc["status"],
        version=doc.get("version", 1),
        metadata=doc.get("metadata", {}),
        review_status=doc.get("review_status"),
        reviewed_by=doc.get("reviewed_by"),
        reviewed_at=doc.get("reviewed_at"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.post("", response_model=TestcaseOut, status_code=201)
async def create_testcase(payload: TestcaseCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)


@router.get("", response_model=list[TestcaseOut])
async def list_testcases(
    requirement_id: str | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if requirement_id:
        filt["requirement_id"] = requirement_id
    if status:
        filt["status"] = status
    if review_status:
        filt["review_status"] = review_status
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"gherkin": {"$regex": q, "$options": "i"}}]
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]


@router.get("/{testcase_id}", response_model=TestcaseOut)
async def get_testcase(testcase_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(testcase_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return to_out(doc)


@router.put("/{testcase_id}", response_model=TestcaseOut)
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


@router.delete("/{testcase_id}", status_code=204)
async def delete_testcase(testcase_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(testcase_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return None


@router.post("/{testcase_id}/approve", response_model=TestcaseOut)
async def approve_testcase(testcase_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(testcase_id)},
        {"$set": {"review_status": "approved", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return to_out(result)


@router.post("/{testcase_id}/reject", response_model=TestcaseOut)
async def reject_testcase(testcase_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(testcase_id)},
        {"$set": {"review_status": "rejected", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return to_out(result)
