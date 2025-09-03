"""
Product Recommendation Workflow Graph
Encapsulates the complete product recommendation pipeline as a subgraph
"""

from langgraph.graph import StateGraph, END
from src.agent.graph_state import GraphState
from .search_products_node import search_products_node
from .formulate_response_node import formulate_response_node

# Global compiled graph - initialized once
_product_recommendation_graph = None


def create_product_recommendation_graph():
    """
    Create and compile the product recommendation workflow graph.
    Simplified flow: search_products -> formulate_response
    """
    graph = StateGraph(GraphState)
    
    # Add simplified product recommendation nodes
    graph.add_node("search_products", search_products_node)
    graph.add_node("formulate_response", formulate_response_node)
    
    # Helper function to check for errors
    def has_error(state):
        return state.error is not None
    
    # Set entry point
    graph.set_entry_point("search_products")
    
    # Add edge with error handling
    graph.add_conditional_edges(
        "search_products",
        has_error,
        {
            True: END,  # Exit on error
            False: "formulate_response"  # Continue to response formulation
        }
    )
    
    # Final node always goes to END
    graph.add_edge("formulate_response", END)
    
    # Compile the graph
    return graph.compile()


def get_product_recommendation_graph():
    """
    Get the compiled product recommendation graph.
    Creates it once on first call and reuses the compiled version.
    
    Returns:
        Compiled StateGraph for product recommendations
    """
    global _product_recommendation_graph
    if _product_recommendation_graph is None:
        _product_recommendation_graph = create_product_recommendation_graph()
    return _product_recommendation_graph


# Optional: Direct invocation function for testing
async def run_product_recommendation(state: GraphState) -> GraphState:
    """
    Run the product recommendation workflow directly.
    Useful for testing or when you want to invoke the workflow programmatically.
    
    Args:
        state: Initial GraphState with session_id, tenant_id, and chat_messages
    """
    graph = get_product_recommendation_graph()
    result = await graph.ainvoke(state.model_dump())
    return GraphState.model_validate(result)