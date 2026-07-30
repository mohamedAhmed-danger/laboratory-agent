
import os
import logging

from knowledge.schemas import EntityType
from .exact_search import exact_search
from .alias_search import alias_search
from .fuzzy_search import fuzzy_search
from .semantic_search import semantic_search
from .merger import merge_results
from .schemas import SearchResult

logger = logging.getLogger(__name__)


def run_search(
    query: str,
    entity_types: list[EntityType] | None = None,
    top_k: int = 5,
) -> dict:

    if not query or not query.strip():
        return {
            "results": [],
            "top_score": 0.0,
        }

    merged = merge_results(
        exact_search(query, entity_types),
        alias_search(query, entity_types),
        fuzzy_search(query, entity_types),
        semantic_search(query, entity_types),
    )

    ranked = sorted(
        merged,
        key=lambda x: x.score,
        reverse=True,
    )[:top_k]

    return {
        "results": ranked,
        "top_score": ranked[0].score if ranked else 0.0,
    }