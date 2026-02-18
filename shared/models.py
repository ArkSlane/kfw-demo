from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

# ---------- Requirements ----------
class RequirementCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = Field(None, max_length=50000)
    source: Optional[str] = Field(None, max_length=100)  # e.g. "code-analysis", "manual", "jira"
    tags: List[str] = Field(default=[], max_length=50)
    release_id: Optional[str] = Field(None, max_length=50)

class RequirementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = Field(None, max_length=50000)
    source: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(None, max_length=50)
    release_id: Optional[str] = Field(None, max_length=50)

class RequirementOut(RequirementCreate):
    id: str
    created_at: datetime
    updated_at: datetime

# ---------- Testcases ----------
TestcaseStatus = Literal["draft", "ready", "passed", "failed", "approved", "inactive"]

class TestcaseCreate(BaseModel):
    requirement_id: str = Field(..., max_length=50)
    title: str = Field(..., max_length=500)
    gherkin: str = Field(..., max_length=100000)
    status: TestcaseStatus = "draft"
    version: int = Field(1, ge=1, le=10000)
    metadata: dict = {}

class TestcaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    gherkin: Optional[str] = Field(None, max_length=100000)
    status: Optional[TestcaseStatus] = None
    version: Optional[int] = Field(None, ge=1, le=10000)
    metadata: Optional[dict] = None

class TestcaseOut(TestcaseCreate):
    id: str
    created_at: datetime
    updated_at: datetime

# ---------- Generator ----------
class GenerateRequest(BaseModel):
    requirement_id: str = Field(..., max_length=50)
    mode: Literal["replace", "append"] = "append"  # how to store results
    amount: int = Field(1, ge=1, le=10)

class GenerateResult(BaseModel):
    generated: List[TestcaseOut]

# ---------- Releases ----------
class ReleaseCreate(BaseModel):
    name: str = Field(..., max_length=200)  # e.g. "2026.01"
    description: Optional[str] = Field(None, max_length=10000)
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    requirement_ids: List[str] = Field(default=[], max_length=500)
    testcase_ids: List[str] = Field(default=[], max_length=2000)

class ReleaseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=10000)
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    requirement_ids: Optional[List[str]] = Field(None, max_length=500)
    testcase_ids: Optional[List[str]] = Field(None, max_length=2000)

class ReleaseOut(ReleaseCreate):
    id: str
    created_at: datetime
    updated_at: datetime
