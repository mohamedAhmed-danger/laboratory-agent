from sqlalchemy import text
from rapidfuzz import fuzz

from knowledge.utils import main_session
from knowledge.schemas import EntityType
from search.preprocess.normalize import normalize
from search.preprocess.ngram import ngram_similarity
from ..schemas import SearchResult

TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}

MIN_SCORE = 0.45  # final score (0-1)


def fuzzy_search(
    query: str,
    aliases: list[str] | None = None,
    entity_types: list[EntityType] | None = None,
    limit: int = 2,
) -> list[SearchResult]:

    normalized_query = normalize(query)

    if not normalized_query:
        return []

    results = []

    types_to_search = entity_types or [
        EntityType.LAB,
        EntityType.BUNDLE,
    ]

    with main_session() as session:

        for entity_type in types_to_search:

            table = TABLE_BY_TYPE[entity_type]

            rows = session.execute(
                text(f"""
                    SELECT id,name
                    FROM {table}
                """)
            ).fetchall()

            scored = []

            for row in rows:

                normalized_name = normalize(row.name)

                rapid = max(
                    fuzz.partial_ratio(normalized_query, normalized_name),
                    fuzz.token_set_ratio(normalized_query, normalized_name),
                ) / 100

                ngram = ngram_similarity(
                    normalized_query,
                    normalized_name,
                )

                final_score = (rapid + ngram) / 2

                if final_score >= MIN_SCORE:

                    scored.append(
                        (
                            row,
                            rapid,
                            ngram,
                            final_score,
                        )
                    )

            scored.sort(
                key=lambda x: x[3],
                reverse=True,
            )

            for row, rapid, ngram, final_score in scored[:limit]:

                results.append(
                    SearchResult(
                        id=row.id,
                        type=entity_type,
                        name=row.name,
                        score=round(final_score, 3),
                        source="fuzzy",
                    )
                )

    results.sort(
        key=lambda x: x.score,
        reverse=True,
    )


    
    return results[:limit]
    


