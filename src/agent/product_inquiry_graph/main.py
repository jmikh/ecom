"""
Product Inquiry Workflow Graph
Handles specific product questions and inquiries with multi-step identification
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from src.agent.graph_state import GraphState
from .identify_product_node import identify_product_node
from .fetch_product_details_node import fetch_product_details_node
from .answer_product_question_node import answer_product_question_node


def should_fetch_details(state: GraphState) -> Literal["fetch_details", "end"]:
    """
    Conditional edge: Decide whether to fetch product details or end
    """
    if state.workflow_params.get('needs_clarification', False):
        # Already sent clarification message with product cards
        return "end"
    
    if state.workflow_params.get('identified_product_ids'):
        # Have product IDs, fetch their details
        return "fetch_details"
    
    return "end"


def should_answer_question(state: GraphState) -> Literal["answer_question", "end"]:
    """
    Conditional edge: Decide whether to answer the question or end
    """
    if state.workflow_params.get('needs_clarification', False):
        return "end"
    
    if state.workflow_params.get('selected_product'):
        return "answer_question"
    
    return "end"


def create_product_inquiry_graph():
    """
    Create and compile the product inquiry workflow graph.
    
    Flow:
    1. identify_product -> (conditional) -> fetch_details or END
    2. fetch_details -> (conditional) -> answer_question or END
    3. answer_question -> END
    """
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("identify_product", identify_product_node)
    graph.add_node("fetch_details", fetch_product_details_node)
    graph.add_node("answer_question", answer_product_question_node)
    
    # Set entry point
    graph.set_entry_point("identify_product")
    
    # Add conditional edges
    graph.add_conditional_edges(
        "identify_product",
        should_fetch_details,
        {
            "fetch_details": "fetch_details",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "fetch_details",
        should_answer_question,
        {
            "answer_question": "answer_question",
            "end": END
        }
    )
    
    # answer_question always goes to END
    graph.add_edge("answer_question", END)
    
    # Compile the graph
    return graph.compile()


# Global compiled graph - initialized once
_product_inquiry_graph = None


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