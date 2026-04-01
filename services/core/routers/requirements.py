from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from shared.db import get_db
from shared.models import RequirementCreate, RequirementUpdate, RequirementOut

router = APIRouter(prefix="/requirements", tags=["requirements"])

COL = "requirements"


def oid(id_: str) -> ObjectId:
    try:
        return ObjectId(id_)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now():
    return datetime.now(timezone.utc)


def to_out(doc) -> RequirementOut:
    return RequirementOut(
        id=str(doc["_id"]),
        title=doc["title"],
        description=doc.get("description"),
        source=doc.get("source"),
        tags=doc.get("tags", []),
        release_id=doc.get("release_id"),
        review_status=doc.get("review_status"),
        reviewed_by=doc.get("reviewed_by"),
        reviewed_at=doc.get("reviewed_at"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.post("", response_model=RequirementOut, status_code=201)
async def create_requirement(payload: RequirementCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)


@router.get("", response_model=list[RequirementOut])
async def list_requirements(
    q: str | None = Query(None),
    review_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]
    if review_status:
        filt["review_status"] = review_status
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]


@router.get("/{requirement_id}", response_model=RequirementOut)
async def get_requirement(requirement_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(requirement_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return to_out(doc)


@router.put("/{requirement_id}", response_model=RequirementOut)
async def update_requirement(requirement_id: str, payload: RequirementUpdate):
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    patch["updated_at"] = now()
    res = await db[COL].update_one({"_id": oid(requirement_id)}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Requirement not found")
    doc = await db[COL].find_one({"_id": oid(requirement_id)})
    return to_out(doc)


@router.delete("/{requirement_id}", status_code=204)
async def delete_requirement(requirement_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(requirement_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return None


@router.post("/{requirement_id}/approve", response_model=RequirementOut)
async def approve_requirement(requirement_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(requirement_id)},
        {"$set": {"review_status": "approved", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return to_out(result)


@router.post("/{requirement_id}/reject", response_model=RequirementOut)
async def reject_requirement(requirement_id: str, reviewed_by: str = Query(...)):
    db = get_db()
    result = await db[COL].find_one_and_update(
        {"_id": oid(requirement_id)},
        {"$set": {"review_status": "rejected", "reviewed_by": reviewed_by, "reviewed_at": now(), "updated_at": now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return to_out(result)
