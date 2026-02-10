from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

# ---------- Requirements ----------
class RequirementCreate(BaseModel):
    title: str = Field(..., min_length=3)
    description: Optional[str] = None
    source: Optional[str] = None  # e.g. "code-analysis", "manual", "jira"
    tags: List[str] = []
    release_id: Optional[str] = None

class RequirementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3)
    description: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    release_id: Optional[str] = None

class RequirementOut(RequirementCreate):
    id: str
    created_at: datetime
    updated_at: datetime

# ---------- Testcases ----------
TestcaseStatus = Literal["draft", "ready", "passed", "failed", "approved", "inactive"]

class TestcaseCreate(BaseModel):
    requirement_id: str
    title: str
    gherkin: str
    status: TestcaseStatus = "draft"
    version: int = 1
    metadata: dict = {}

class TestcaseUpdate(BaseModel):
    title: Optional[str] = None
    gherkin: Optional[str] = None
    status: Optional[TestcaseStatus] = None
    version: Optional[int] = None
    metadata: Optional[dict] = None

class TestcaseOut(TestcaseCreate):
    id: str
    created_at: datetime
    updated_at: datetime

# ---------- Generator ----------
class GenerateRequest(BaseModel):
    requirement_id: str
    mode: Literal["replace", "append"] = "append"  # how to store results
    amount: int = Field(1, ge=1, le=10)

class GenerateResult(BaseModel):
    generated: List[TestcaseOut]

# ---------- Releases ----------
class ReleaseCreate(BaseModel):
    name: str  # e.g. "2026.01"
    description: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    requirement_ids: List[str] = []
    testcase_ids: List[str] = []

class ReleaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    requirement_ids: Optional[List[str]] = None
    testcase_ids: Optional[List[str]] = None

class ReleaseOut(ReleaseCreate):
    id: str
    created_at: datetime
    updated_at: datetime
