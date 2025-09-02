"""
Product Recommendation Workflow Graph
Encapsulates the complete product recommendation pipeline as a subgraph
"""

from langgraph.graph import StateGraph, END
from src.agent.graph_state import GraphState
from src.agent import get_product_filters_node, fetch_candidate_products_node, validate_recommended_products_node

# Global compiled graph - initialized once
_product_recommendation_graph = None


def create_product_recommendation_graph():
    """
    Create and compile the product recommendation workflow graph.
    This graph handles the complete flow from filter extraction to product validation.
    """
    graph = StateGraph(GraphState)
    
    # Add all product recommendation nodes
    graph.add_node("get_filters", get_product_filters_node.get_product_filters_node)
    graph.add_node("fetch_candidates", fetch_candidate_products_node.fetch_candidate_products_node)
    graph.add_node("validate_products", validate_recommended_products_node.validate_recommended_products_node)
    
    # Helper function to check for errors
    def has_error(state):
        return state.error is not None
    
    # Set entry point
    graph.set_entry_point("get_filters")
    
    # Add edges with error handling
    # If error occurs at any stage, exit the workflow
    graph.add_conditional_edges(
        "get_filters",
        has_error,
        {
            True: END,  # Exit on error
            False: "fetch_candidates"  # Continue to fetch
        }
    )
    
    graph.add_conditional_edges(
        "fetch_candidates", 
        has_error,
        {
            True: END,  # Exit on error
            False: "validate_products"  # Continue to validation
        }
    )
    
    # Final node always goes to END
    graph.add_edge("validate_products", END)
    
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
        
    Returns:
        Updated GraphState with products_filter, finalist_products, and final_answer
    """
    graph = get_product_recommendation_graph()
    result = await graph.ainvoke(state.model_dump())
    return GraphState.model_validate(result)