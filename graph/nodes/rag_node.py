from graph.state import AgentState
from search.search_manager import run_search
from rag.context_builder import build_context


def rag_node(state: AgentState):

    query = state.get("refined_query") or state["user_message"]

    search = run_search(query)

    results = search["results"]

    return {
        "rag_context": build_context(results),
        "search_results": results,
        "top_score": search["top_score"],
    }