import logging

from sqlalchemy import text

from knowledge.utils import vector_session, get_gemini_client
from knowledge.schemas import EntityType
from ..schemas import SearchResult

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768


def _embed_query(text_to_embed: str) -> list[float]:

    client = get_gemini_client()

    if hasattr(client, "models"):
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text_to_embed,
            config={
                "output_dimensionality": EMBEDDING_DIM,
                "task_type": "retrieval_query",
            },
        )

        return response.embeddings[0].values

    response = client.embed_content(
        model=EMBEDDING_MODEL,
        content=text_to_embed,
        task_type="retrieval_query",
        output_dimensionality=EMBEDDING_DIM,
    )

    return response["embedding"]


def _to_pgvector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


def semantic_search(
    query: str,
    description: str | None = None,
    entity_types: list[EntityType] | None = None,
    limit: int = 5,
) -> list[SearchResult]:

    if not query.strip():
        return []

    search_text = query.strip()

    if description:
        search_text += "\n" + description.strip()

    try:
        query_vector = _to_pgvector_literal(
            _embed_query(search_text)
        )

    except Exception as exc:
        logger.warning(
            "[Semantic Search] Embedding generation failed: %s",
            exc,
        )
        return []

    types_to_search = entity_types or [
        EntityType.LAB,
        EntityType.BUNDLE,
    ]

    type_values = [t.value for t in types_to_search]

    results: list[SearchResult] = []

    try:

        with vector_session() as session:

            rows = session.execute(
                text("""
                    SELECT
                        id,
                        type,
                        name,
                        1 - (embedding <=> CAST(:query_vector AS vector)) AS similarity
                    FROM knowledge_vectors
                    WHERE type = ANY(:types)
                    ORDER BY embedding <=> CAST(:query_vector AS vector)
                    LIMIT :limit
                """),
                {
                    "query_vector": query_vector,
                    "types": type_values,
                    "limit": limit,
                },
            ).fetchall()

            for row in rows:

                results.append(
                    SearchResult(
                        id=row.id,
                        type=EntityType(row.type),
                        name=row.name,
                        score=round(float(row.similarity), 3),
                        source="semantic",
                    )
                )

    except Exception as exc:

        logger.warning(
            "[Semantic Search] Vector search failed: %s",
            exc,
        )

    return results