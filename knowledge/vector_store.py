
import logging

from sqlalchemy import text

from .schemas import EntityType, VectorMetadata
from .utils import vector_session

logger = logging.getLogger(__name__)


def ensure_vector_table() -> None:
    """Ensures vector extension and knowledge_vectors table exist in PostgreSQL."""
    try:
        with vector_session() as session:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_vectors (
                    id INT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    embedding vector(768),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (id, type)
                );
            """))
    except Exception as e:
        logger.warning("Failed to initialize vector table: %s", e)


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