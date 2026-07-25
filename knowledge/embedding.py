"""
embedding.py
Generates embeddings for approved knowledge using Gemini's gemini-embedding-001 model.

Embedding input = Name + Description + Keywords + Aliases (combined into search_text).
"""

import logging

from .schemas import ApprovedKnowledge
from .utils import get_gemini_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768  


def build_embedding_text(name: str, approved: ApprovedKnowledge) -> str:
    """Combines Name + Description + Keywords + Aliases into search_text string."""
    if approved.search_text:
        return approved.search_text
    aliases_str = ", ".join(approved.aliases) if isinstance(approved.aliases, list) else str(approved.aliases or "")
    keywords_str = ", ".join(approved.keywords) if isinstance(approved.keywords, list) else str(approved.keywords or "")
    return f"{name}\n{approved.description}\nالمرادفات والأسماء البديلة: {aliases_str}\nالكلمات المفتاحية: {keywords_str}".strip()


def generate_embedding(name: str, approved: ApprovedKnowledge) -> list[float]:
    """Calls Gemini to embed the combined knowledge search_text. Returns a vector."""
    client_or_genai = get_gemini_client()
    text_input = build_embedding_text(name, approved)

    if hasattr(client_or_genai, "models"):
        res = client_or_genai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text_input,
        )
        embedding = res.embeddings[0].values
    else:
        result = client_or_genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text_input,
            task_type="retrieval_document",
            title=name,
            output_dimensionality=EMBEDDING_DIM,
        )
        embedding = result["embedding"]

    logger.info("Generated embedding of length %s for '%s'", len(embedding), name)
    return embedding