"""
Main Graph Composition for Mission Control Agent
Builds the LangGraph workflow that handles intent classification and routing
"""

from langgraph.graph import StateGraph, END
from src.agent import classify_intent_node, error_node
from src.agent.product_recommendation_graph import get_product_recommendation_graph
from src.agent.product_inquiry_graph import get_product_inquiry_graph
from src.agent.store_brand_graph import get_store_brand_graph
from src.agent.unrelated_graph import get_unrelated_graph
from src.agent.graph_state import GraphState, UserIntent

# Global compiled graph - initialized once
_compiled_graph = None

def get_main_graph() -> StateGraph:
    """Get the compiled graph, creating it once if needed"""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(GraphState)
    
    # Add nodes - use global node functions
    graph.add_node("classify_intent", classify_intent_node.classify_intent_node)
    graph.add_node("error", error_node.error_node)
    
    # Add all workflow subgraphs as single nodes
    graph.add_node("product_recommendation", get_product_recommendation_graph())
    graph.add_node("product_inquiry", get_product_inquiry_graph())
    graph.add_node("store_brand", get_store_brand_graph())
    graph.add_node("unrelated", get_unrelated_graph())
    
    # Add conditional routing for error handling and intent workflows
    def get_next_hop(state):
        # Check for errors first
        if state.error:
            return "error"
        
        intent = state.intent_decision.intent
        if intent == UserIntent.PRODUCT_RECOMMENDATION:
            return "product_recommendation"
        elif intent == UserIntent.PRODUCT_INQUIRY:
            return "product_inquiry"
        elif intent == UserIntent.STORE_BRAND_QUESTION:
            return "store_brand"
        elif intent == UserIntent.UNRELATED:
            return "unrelated"
        
    

    # Add edges
    graph.set_entry_point("classify_intent")
    
    # Add conditional edges from classify_intent
    graph.add_conditional_edges(
        "classify_intent",
        get_next_hop,
        {
            "error": "error",
            "product_recommendation": "product_recommendation",
            "product_inquiry": "product_inquiry",
            "store_brand": "store_brand",
            "unrelated": "unrelated"
        }
    )

    # Add edges from workflow nodes to END
    # All subgraphs handle their own internal routing
    workflow_nodes = [
        "product_recommendation",
        "product_inquiry", 
        "store_brand",
        "unrelated",
        "error"
    ]
    
    for node in workflow_nodes:
        graph.add_edge(node, END)
    
    _compiled_graph = graph.compile()
    return _compiled_graph