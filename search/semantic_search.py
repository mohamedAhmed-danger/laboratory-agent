
import logging

from sqlalchemy import text

from knowledge.utils import vector_session, get_gemini_client
from knowledge.schemas import EntityType
from .schemas import SearchResult

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768  # must match the dimension used in knowledge/embedding.py


def _embed_query(query: str) -> list[float]:
  
    client_or_genai = get_gemini_client()

    if hasattr(client_or_genai, "models"):
        res = client_or_genai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config={"output_dimensionality": EMBEDDING_DIM, "task_type": "retrieval_query"},
        )
        return res.embeddings[0].values
    else:
        result = client_or_genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query,
            task_type="retrieval_query",
            output_dimensionality=EMBEDDING_DIM,
        )
        return result["embedding"]


def _to_pgvector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"

def semantic_search(query: str, entity_types: list[EntityType] | None = None,
                     limit: int = 10) -> list[SearchResult]:
  
    if not query.strip():
        return []

    try:
        query_vector = _to_pgvector_literal(_embed_query(query))
    except Exception as e:
        logger.warning("[Semantic Search] Embedding generation failed: %s", e)
        return []

    types_to_search = entity_types or [EntityType.LAB, EntityType.BUNDLE]
    type_values = [t.value for t in types_to_search]



    results: list[SearchResult] = []
    try:
        with vector_session() as session:
            rows = session.execute(
                text("""
                    SELECT id, type, name, 1 - (embedding <=> CAST(:qvec AS vector)) AS similarity
                    FROM knowledge_vectors
                    WHERE type = ANY(:types)
                    ORDER BY embedding <=> CAST(:qvec AS vector)
                    LIMIT :limit
                """),
                {"qvec": query_vector, "types": type_values, "limit": limit},
            ).fetchall()

            for row in rows:
                results.append(SearchResult(
                    id=row.id, type=EntityType(row.type), name=row.name,
                    score=round(float(row.similarity), 3), source="vector"
                ))
    except Exception as exc:
        logger.warning("[Semantic Search] Vector query failed (table may be empty): %s", exc)

    return results