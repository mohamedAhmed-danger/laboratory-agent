
import logging

from sqlalchemy import text

from .schemas import EntityType, VectorMetadata
from .utils import vector_session

logger = logging.getLogger(__name__)


def _to_pgvector_literal(embedding: list[float]) -> str:
    """pgvector expects a string like '[0.1,0.2,0.3]'."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def upsert_vector(metadata: VectorMetadata, embedding: list[float]) -> None:
    """
    Inserts a new embedding or updates the existing one for (id, type).
    Metadata written is strictly {id, type, name} per spec.
    """
    vector_literal = _to_pgvector_literal(embedding)

    with vector_session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_vectors (id, type, name, embedding, updated_at)
                VALUES (:id, :type, :name, CAST(:embedding AS vector), now())
                ON CONFLICT (id, type)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
            """),
            {
                "id": metadata.id,
                "type": metadata.type.value,
                "name": metadata.name,
                "embedding": vector_literal,
            },
        )
    logger.info("Upserted vector for %s id=%s", metadata.type.value, metadata.id)


def delete_vector(entity_id: int, entity_type: EntityType) -> None:
    """Removes a vector, e.g. if the Lab/Bundle is deleted."""
    with vector_session() as session:
        session.execute(
            text("DELETE FROM knowledge_vectors WHERE id = :id AND type = :type"),
            {"id": entity_id, "type": entity_type.value},
        )
    logger.info("Deleted vector for %s id=%s", entity_type.value, entity_id)