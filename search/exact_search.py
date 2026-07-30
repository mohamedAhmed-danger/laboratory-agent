from sqlalchemy import text

from knowledge.utils import main_session
from knowledge.schemas import EntityType
from .schemas import SearchResult

TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}


def exact_search(query: str, entity_types: list[EntityType] | None = None) -> list[SearchResult]:
    """
    Case-insensitive exact match on name, across labs and/or bundles.
    Pass entity_types=[EntityType.LAB] to search only labs, etc.
    Defaults to searching both.
    """
    normalized = query.strip().lower()
    if not normalized:
        return []

    types_to_search = entity_types or [EntityType.LAB, EntityType.BUNDLE]
    results: list[SearchResult] = []

    with main_session() as session:
        for entity_type in types_to_search:
            table = TABLE_BY_TYPE[entity_type]
            rows = session.execute(
                text(f"SELECT id, name FROM {table} WHERE lower(name) = :q"),
                {"q": normalized},
            ).fetchall()

            for row in rows:
                results.append(SearchResult(
                    id=row.id, type=entity_type, name=row.name, score=1.0, source="exact"
                ))

    return results