"""
schemas.py
Pydantic models used to validate data at every stage of the pipeline.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EntityType(str, Enum):
    LAB = "lab"
    BUNDLE = "bundle"


# ---------------------------------------------------------------------------
# Step 1 - Duplicate Checker
# ---------------------------------------------------------------------------
class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    matched_id: Optional[int] = None
    matched_name: Optional[str] = None
    score: float = 0.0


# ---------------------------------------------------------------------------
# Step 2 - Knowledge Generator (input)
# ---------------------------------------------------------------------------
class KnowledgeGenerationRequest(BaseModel):
    name: str
    patient_instructions: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[float] = None
    entity_type: EntityType = EntityType.LAB


# ---------------------------------------------------------------------------
# Step 2 - Knowledge Generator (output) / Step 4 - Review Page payload
# ---------------------------------------------------------------------------
class GeneratedKnowledge(BaseModel):
    description: str
    aliases: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    search_text: str

    @field_validator("description", "search_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Step 3 - Validator output
# ---------------------------------------------------------------------------
class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 4/5 - What the admin actually approves (may be edited from the
# originally generated knowledge)
# ---------------------------------------------------------------------------
class ApprovedKnowledge(GeneratedKnowledge):
    entity_id: int
    entity_type: EntityType


# ---------------------------------------------------------------------------
# Step 7 - Vector store metadata (kept minimal on purpose)
# ---------------------------------------------------------------------------
class VectorMetadata(BaseModel):
    id: int
    type: EntityType
    name: str