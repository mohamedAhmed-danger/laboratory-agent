"""
embedding.py
Generates embeddings for approved knowledge using Gemini's embedding model.

Embedding input = Name + Description + Keywords + Aliases (concatenated
into one text blob, per spec).
"""

import logging

from .schemas import ApprovedKnowledge
from .utils import get_gemini_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768  


def build_embedding_text(name: str, approved: ApprovedKnowledge) -> str:
    """Combines Name + Description + Keywords + Aliases into one string."""
    parts = [
        name,
        approved.description,
        ", ".join(approved.keywords),
        ", ".join(approved.aliases),
    ]
    return "\n".join(p for p in parts if p)


def generate_embedding(name: str, approved: ApprovedKnowledge) -> list[float]:
    """Calls Gemini to embed the combined knowledge text. Returns a vector."""
    genai = get_gemini_client()
    text_input = build_embedding_text(name, approved)

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text_input,
        task_type="retrieval_document",
        title=name,
        output_dimensionality=EMBEDDING_DIM,
    )
    embedding = result["embedding"]
    logger.info("Generated embedding of length %s for '%s'", len(embedding), name)
    return embedding