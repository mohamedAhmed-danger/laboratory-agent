
from sqlalchemy import text
from rapidfuzz import fuzz

from knowledge.utils import main_session
from knowledge.schemas import EntityType
from .schemas import SearchResult

TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}

MIN_SCORE = 55  # 0-100 scale - below this, it's not worth returning


def fuzzy_search(query: str, entity_types: list[EntityType] | None = None,
                  limit: int = 10) -> list[SearchResult]:
    """
    Returns up to `limit` fuzzy matches per entity type, sorted by score.
    Uses the best of partial_ratio (substring match, catches "cbc" inside
    a longer name) and token_set_ratio (word-order independent).
    """
    normalized = query.strip().lower()
    if not normalized:
        return []

    types_to_search = entity_types or [EntityType.LAB, EntityType.BUNDLE]
    results: list[SearchResult] = []

    with main_session() as session:
        for entity_type in types_to_search:
            table = TABLE_BY_TYPE[entity_type]
            rows = session.execute(text(f"SELECT id, name FROM {table}")).fetchall()

            scored = []
            for row in rows:
                name_lower = row.name.lower()
                score = max(
                    fuzz.partial_ratio(normalized, name_lower),
                    fuzz.token_set_ratio(normalized, name_lower),
                )
                if score >= MIN_SCORE:
                    scored.append((row, score))

            scored.sort(key=lambda pair: pair[1], reverse=True)
            for row, score in scored[:limit]:
                results.append(SearchResult(
                    id=row.id, type=entity_type, name=row.name,
                    score=round(score / 100, 3), source="fuzzy"
                ))

    return results