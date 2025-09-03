"""
Unrelated Query Workflow Graph
Handles queries that don't relate to products or the store
"""

from langgraph.graph import StateGraph, END
from src.agent.graph_state import GraphState

# Global compiled graph - initialized once
_unrelated_graph = None


def unrelated_node(state: GraphState) -> GraphState:
    """
    Placeholder node for unrelated queries.
    Will handle general conversation, greetings, or redirect users to product-related topics.
    """
    print(f"\n{'='*60}")
    print(f"🤷 UNRELATED_WORKFLOW: Processing unrelated query")
    print(f"{'='*60}")
    
    # Set response using ChatServerResponse to redirect to product topics
    from src.shared.schemas import ChatServerResponse
    state.chat_server_response = ChatServerResponse(
        message="I'm here to help you find products! Could you tell me what kind of items you're looking for today? I can help you find clothing, accessories, bags, or other products from our catalog."
    )
    
    return state


def create_unrelated_graph():
    """
    Create and compile the unrelated query workflow graph.
    """
    graph = StateGraph(GraphState)
    
    # Add single placeholder node for now
    graph.add_node("unrelated", unrelated_node)
    
    # Set entry point and exit
    graph.set_entry_point("unrelated")
    graph.add_edge("unrelated", END)
    
    # Compile the graph
    return graph.compile()


def get_unrelated_graph():
    """
    Get the compiled unrelated query graph.
    Creates it once on first call and reuses the compiled version.
    
    Returns:
        Compiled StateGraph for unrelated queries
    """
    global _unrelated_graph
    if _unrelated_graph is None:
        _unrelated_graph = create_unrelated_graph()
    return _unrelated_graph