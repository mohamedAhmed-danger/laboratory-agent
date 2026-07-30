from search.search_manager import run_search

from .context_builder import build_context
from .schemas import RetrievalResult


def retrieve(query: str):

    search = run_search(query)

    context = build_context(
        search["results"]
    )

    return RetrievalResult(
        results=search["results"],
        context=context,
        top_score=search["top_score"],
    )