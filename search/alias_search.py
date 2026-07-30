
from sqlalchemy import text

from knowledge.utils import main_session
from knowledge.schemas import EntityType
from .schemas import SearchResult

TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}


def alias_search(query: str, entity_types: list[EntityType] | None = None) -> list[SearchResult]:
    """
    Substring match against alias_names (stored as a comma-separated
    string, per how updater.py writes it). Score is slightly below
    exact since it's a looser match.
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
                text(f"""
                    SELECT id, name FROM {table}
                    WHERE alias_names IS NOT NULL
                      AND lower(alias_names) LIKE :pattern
                """),
                {"pattern": f"%{normalized}%"},
            ).fetchall()

            for row in rows:
                results.append(SearchResult(
                    id=row.id, type=entity_type, name=row.name, score=0.95, source="alias"
                ))

    return results