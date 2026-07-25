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
    entity_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Step 2 - Knowledge Generator (output) / Step 4 - Review Page payload
# ---------------------------------------------------------------------------
class GeneratedKnowledge(BaseModel):
    description: str
    aliases: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    search_text: Optional[str] = ""

    def construct_search_text(self, item_name: str) -> str:
        aliases_str = ", ".join(self.aliases) if isinstance(self.aliases, list) else str(self.aliases or "")
        keywords_str = ", ".join(self.keywords) if isinstance(self.keywords, list) else str(self.keywords or "")
        self.search_text = f"{item_name}\n{self.description}\nالمرادفات والأسماء البديلة: {aliases_str}\nالكلمات المفتاحية: {keywords_str}".strip()
        return self.search_text


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