from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from shared.db import get_db, close_client
from shared.models import RequirementCreate, RequirementUpdate, RequirementOut
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
    """Startup / shutdown lifecycle."""
    setup_logging("requirements", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    validate_settings()
    await ensure_indexes(get_db(), ["requirements"])
    logger.info("Requirements service ready")
    yield
    await close_client()
    logger.info("Requirements service stopped")


app = FastAPI(
    lifespan=lifespan,
    title="Requirements Management Service",
    version="1.0.0",
    description="""CRUD service for managing requirements used by testcase generation and management.
    
    ## Features
    - Create, read, update, and delete requirements
    - Search requirements by text
    - Link requirements to releases
    - Tag-based organization
    - Support for multiple requirement sources (JIRA, manual, code-analysis)
    
    ## Use Cases
    - Store product requirements and user stories
    - Generate test cases from requirements using AI
    - Organize requirements by release
    - Track requirement metadata and sources
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "requirements", "description": "Operations on requirements"},
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
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

@app.get(
    "/health",
    tags=["health"],
    summary="Service Health Check",
    description="Check service health and dependency status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "requirements",
                        "timestamp": "2025-12-14T10:30:00Z",
                        "dependencies": {
                            "mongodb": {
                                "status": "healthy",
                                "message": "Connected to database: aitp",
                                "response_time_ms": 5
                            }
                        }
                    }
                }
            }
        }
    }
)
async def health():
    """Check service health and all dependency statuses."""
    # Check dependencies
    dependencies = {
        "mongodb": await check_mongodb(MONGO_URL, DB_NAME)
    }
    
    overall_status = aggregate_health_status(dependencies)
    
    return {
        "status": overall_status,
        "service": "requirements",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies
    }

@app.post(
    "/requirements",
    response_model=RequirementOut,
    status_code=201,
    tags=["requirements"],
    summary="Create New Requirement",
    description="Create a new requirement with title, description, source, tags, and optional release link",
    responses={
        201: {
            "description": "Requirement created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "507f1f77bcf86cd799439011",
                        "title": "User Authentication",
                        "description": "Users must be able to login with email and password",
                        "source": "jira",
                        "tags": ["authentication", "security"],
                        "release_id": "507f1f77bcf86cd799439012",
                        "created_at": "2025-12-14T10:30:00Z",
                        "updated_at": "2025-12-14T10:30:00Z"
                    }
                }
            }
        },
        422: {"description": "Validation error - invalid input data"}
    }
)
async def create_requirement(payload: RequirementCreate):
    """Create a new requirement.
    
    Args:
        payload: Requirement data including title (required), description, source, tags, and release_id
    
    Returns:
        The created requirement with generated ID and timestamps
    """
    db = get_db()
    ts = now()
    doc = payload.model_dump()
    doc.update({"created_at": ts, "updated_at": ts})
    res = await db[COL].insert_one(doc)
    created = await db[COL].find_one({"_id": res.inserted_id})
    return to_out(created)

@app.get(
    "/requirements",
    response_model=list[RequirementOut],
    tags=["requirements"],
    summary="List All Requirements",
    description="""Retrieve a list of requirements with optional search and pagination.
    
    - Search by text in title or description
    - Results sorted by most recently updated
    - Pagination support with skip and limit
    """,
    responses={
        200: {
            "description": "List of requirements",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "507f1f77bcf86cd799439011",
                            "title": "User Authentication",
                            "description": "Users must be able to login with email and password",
                            "source": "jira",
                            "tags": ["authentication", "security"],
                            "release_id": "507f1f77bcf86cd799439012",
                            "created_at": "2025-12-14T10:30:00Z",
                            "updated_at": "2025-12-14T10:30:00Z"
                        }
                    ]
                }
            }
        }
    }
)
async def list_requirements(
    q: str | None = Query(None, description="Search text (searches in title and description)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results to return"),
    skip: int = Query(0, ge=0, description="Number of results to skip for pagination"),
):
    """List all requirements with optional filtering and pagination.
    
    Args:
        q: Optional search query (case-insensitive, searches title and description)
        limit: Maximum number of requirements to return (1-200, default: 50)
        skip: Number of requirements to skip for pagination (default: 0)
    
    Returns:
        List of requirements matching the search criteria, sorted by most recently updated
    """
    db = get_db()
    filt = {}
    if q:
        filt = {"$or": [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]}
    cursor = db[COL].find(filt).sort("updated_at", -1).skip(skip).limit(limit)
    return [to_out(d) async for d in cursor]

@app.get(
    "/requirements/{requirement_id}",
    response_model=RequirementOut,
    tags=["requirements"],
    summary="Get Single Requirement",
    description="Retrieve a specific requirement by its ID",
    responses={
        200: {
            "description": "Requirement found",
            "content": {
                "application/json": {
                    "example": {
                        "id": "507f1f77bcf86cd799439011",
                        "title": "User Authentication",
                        "description": "Users must be able to login with email and password",
                        "source": "jira",
                        "tags": ["authentication", "security"],
                        "release_id": "507f1f77bcf86cd799439012",
                        "created_at": "2025-12-14T10:30:00Z",
                        "updated_at": "2025-12-14T10:30:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid requirement ID format"},
        404: {"description": "Requirement not found"}
    }
)
async def get_requirement(requirement_id: str):
    """Get a single requirement by ID.
    
    Args:
        requirement_id: MongoDB ObjectId as string
    
    Returns:
        The requirement with the specified ID
    
    Raises:
        400: If the ID format is invalid
        404: If no requirement exists with the given ID
    """
    db = get_db()
    doc = await db[COL].find_one({"_id": oid(requirement_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return to_out(doc)

@app.put(
    "/requirements/{requirement_id}",
    response_model=RequirementOut,
    tags=["requirements"],
    summary="Update Requirement",
    description="Update one or more fields of an existing requirement. Only provided fields will be updated.",
    responses={
        200: {
            "description": "Requirement updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "507f1f77bcf86cd799439011",
                        "title": "Enhanced User Authentication",
                        "description": "Users must be able to login with email/password and 2FA",
                        "source": "jira",
                        "tags": ["authentication", "security", "2fa"],
                        "release_id": "507f1f77bcf86cd799439012",
                        "created_at": "2025-12-14T10:30:00Z",
                        "updated_at": "2025-12-14T11:00:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid ID or no fields to update"},
        404: {"description": "Requirement not found"}
    }
)
async def update_requirement(requirement_id: str, payload: RequirementUpdate):
    """Update an existing requirement.
    
    Args:
        requirement_id: MongoDB ObjectId as string
        payload: Fields to update (all optional)
    
    Returns:
        The updated requirement
    
    Raises:
        400: If no fields provided or invalid ID
        404: If no requirement exists with the given ID
    """
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

@app.delete(
    "/requirements/{requirement_id}",
    status_code=204,
    tags=["requirements"],
    summary="Delete Requirement",
    description="Permanently delete a requirement. This action cannot be undone.",
    responses={
        204: {"description": "Requirement deleted successfully (no content returned)"},
        400: {"description": "Invalid requirement ID format"},
        404: {"description": "Requirement not found"}
    }
)
async def delete_requirement(requirement_id: str):
    """Delete a requirement permanently.
    
    Args:
        requirement_id: MongoDB ObjectId as string
    
    Returns:
        None (204 No Content)
    
    Raises:
        400: If the ID format is invalid
        404: If no requirement exists with the given ID
    """
    db = get_db()
    res = await db[COL].delete_one({"_id": oid(requirement_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return None
