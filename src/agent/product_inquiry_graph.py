"""
Product Inquiry Workflow Graph
Handles specific product questions and inquiries
"""

from langgraph.graph import StateGraph, END
from src.agent.graph_state import GraphState

# Global compiled graph - initialized once
_product_inquiry_graph = None


def product_inquiry_node(state: GraphState) -> GraphState:
    """
    Placeholder node for product inquiry workflow.
    Will handle questions about specific products, availability, specifications, etc.
    """
    print(f"\n{'='*60}")
    print(f"📦 PRODUCT_INQUIRY_WORKFLOW: Processing product inquiry")
    print(f"{'='*60}")
    
    # Set placeholder response
    state.final_answer = "Product inquiry workflow is currently not supported. This feature will handle specific questions about products, availability, and specifications."
    
    return state


def create_product_inquiry_graph():
    """
    Create and compile the product inquiry workflow graph.
    """
    graph = StateGraph(GraphState)
    
    # Add single placeholder node for now
    graph.add_node("product_inquiry", product_inquiry_node)
    
    # Set entry point and exit
    graph.set_entry_point("product_inquiry")
    graph.add_edge("product_inquiry", END)
    
    # Compile the graph
    return graph.compile()


def get_product_inquiry_graph():
    """
    Get the compiled product inquiry graph.
    Creates it once on first call and reuses the compiled version.
    
    Returns:
        Compiled StateGraph for product inquiries
    """
    global _product_inquiry_graph
    if _product_inquiry_graph is None:
        _product_inquiry_graph = create_product_inquiry_graph()
    return _product_inquiry_graph