from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from shared.db import get_db
from shared.models import ReleaseCreate, ReleaseUpdate, ReleaseOut

router = APIRouter(prefix="/releases", tags=["releases"])

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


@router.post("", response_model=ReleaseOut, status_code=201)
async def create_release(payload: ReleaseCreate):
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)


@router.get("", response_model=list[ReleaseOut])
async def list_releases(
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    filt = {}
    if q:
        filt = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]}
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]


@router.get("/{release_id}", response_model=ReleaseOut)
async def get_release(release_id: str):
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(release_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Release not found")
    return to_out(doc)


@router.put("/{release_id}", response_model=ReleaseOut)
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


@router.delete("/{release_id}", status_code=204)
async def delete_release(release_id: str):
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(release_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Release not found")
    return None
