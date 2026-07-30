

from pydantic import BaseModel
from knowledge.schemas import EntityType


class SearchResult(BaseModel):
    id: int
    type: EntityType
    name: str
    score: float          # normalized 0.0 - 1.0, always, regardless of method
    source: str            # "exact" | "alias" | "fuzzy" | "vector"