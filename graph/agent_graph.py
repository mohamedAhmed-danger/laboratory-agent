from graph.nodes.booking_node import booking_node
from graph.nodes.complaint_node import complaint_node
from graph.nodes.direct_node import direct_node
from graph.nodes.intent_node import intent_node
from graph.nodes.inquiry_node import inquiry_node
from graph.state import AgentState
from langgraph.graph import StateGraph, END

__agent_graph = None


def route_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent in ["booking", "complaint", "direct", "inquiry"]:
        return intent
    return "direct"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    # nodes
    graph.add_node("intent", intent_node)
    graph.add_node("booking", booking_node)
    graph.add_node("complaint", complaint_node)
    graph.add_node("direct", direct_node)
    graph.add_node("inquiry", inquiry_node)
    # entry point
    graph.set_entry_point("intent")
    
    # intent routing
    graph.add_conditional_edges(
        "intent",
        route_intent,
        {
            "booking": "booking",
            "complaint": "complaint",
            "direct": "direct",
            "inquiry": "inquiry",
        }     
    )
    
    graph.add_edge("booking", END)
    graph.add_edge("complaint", END)
    graph.add_edge("direct", END)
    graph.add_edge("inquiry", END)

    return graph.compile() 


def get_agent_graph():
    global __agent_graph
    if __agent_graph is None:    
        __agent_graph = build_graph()   

    return __agent_graph    
