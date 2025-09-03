"""
Store/Brand Question Workflow Graph
Handles questions about the store, brands, policies, etc.
"""

from langgraph.graph import StateGraph, END
from src.agent.graph_state import GraphState

# Global compiled graph - initialized once
_store_brand_graph = None


def store_brand_node(state: GraphState) -> GraphState:
    """
    Placeholder node for store/brand workflow.
    Will handle questions about store policies, brand information, shipping, returns, etc.
    """
    print(f"\n{'='*60}")
    print(f"🏪 STORE_BRAND_WORKFLOW: Processing store/brand question")
    print(f"{'='*60}")
    
    # Set response using ChatServerResponse
    from src.shared.schemas import ChatServerResponse
    state.chat_server_response = ChatServerResponse(
        message="I appreciate your question about our store policies. While I'm currently focused on helping you find products, you can visit our website for detailed information about shipping, returns, and other policies. In the meantime, is there anything specific you're looking to purchase today?"
    )
    
    return state


def create_store_brand_graph():
    """
    Create and compile the store/brand workflow graph.
    """
    graph = StateGraph(GraphState)
    
    # Add single placeholder node for now
    graph.add_node("store_brand", store_brand_node)
    
    # Set entry point and exit
    graph.set_entry_point("store_brand")
    graph.add_edge("store_brand", END)
    
    # Compile the graph
    return graph.compile()


def get_store_brand_graph():
    """
    Get the compiled store/brand graph.
    Creates it once on first call and reuses the compiled version.
    
    Returns:
        Compiled StateGraph for store/brand questions
    """
    global _store_brand_graph
    if _store_brand_graph is None:
        _store_brand_graph = create_store_brand_graph()
    return _store_brand_graph