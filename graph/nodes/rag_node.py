from graph.state import AgentState
from rag.context_builder import build_context
from search.search_manager import run_search


def rag_node(state: AgentState):

    refined_queries = state.get("refined_queries", [])

    search = run_search(refined_queries)

    context = build_context(search["results"])

    return {
        "rag_context": context,
        "search_results": search["results"],
        "top_score": search["top_score"],
    }