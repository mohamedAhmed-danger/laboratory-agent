from graph.nodes.booking_node import booking_node
from graph.nodes.complaint_node import complaint_node
from graph.nodes.direct_node import direct_node
from graph.nodes.intent_node import intent_node
from graph.nodes.inquiry_node import inquiry_node
from graph.nodes.rag_node import rag_node

from graph.state import AgentState

from langgraph.graph import StateGraph, END

__agent_graph = None


def route_intent(state: AgentState):
    return state.get("intent", "direct")


def build_graph():

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("intent", intent_node)
    graph.add_node("rag", rag_node)
    graph.add_node("booking", booking_node)
    graph.add_node("complaint", complaint_node)
    graph.add_node("inquiry", inquiry_node)
    graph.add_node("direct", direct_node)

    graph.set_entry_point("intent")

    # Intent Routing
    graph.add_conditional_edges(
        "intent",
        route_intent,
        {
            "booking": "rag",
            "inquiry": "rag",
            "complaint": "complaint",
            "direct": "direct",
        },
    )

    # After RAG
    graph.add_conditional_edges(
        "rag",
        route_intent,
        {
            "booking": "booking",
            "inquiry": "inquiry",
        },
    )

    graph.add_edge("booking", END)
    graph.add_edge("complaint", END)
    graph.add_edge("inquiry", END)
    graph.add_edge("direct", END)

    return graph.compile()


def get_agent_graph():
    global __agent_graph

    if __agent_graph is None:
        __agent_graph = build_graph()

    return __agent_graph