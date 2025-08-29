"""
Main Graph Composition for Mission Control Agent
Builds the LangGraph workflow that handles intent classification and routing
"""

from langgraph.graph import StateGraph, END
from src.agent import classify_intent_node, get_product_filters_node, fetch_candidate_products_node, error_node
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
    
    # Add nodes for each intent workflow
    graph.add_node("get_product_filters_node", get_product_filters_node.get_product_filters_node)
    graph.add_node("fetch_candidate_products_node", fetch_candidate_products_node.fetch_candidate_products_node)
    graph.add_node("product_inquiry_workflow", lambda state: print(f"\n{'='*60}\n📦 PRODUCT_INQUIRY_WORKFLOW: Processing product inquiry\n{'='*60}") or state)
    graph.add_node("store_brand_workflow", lambda state: print(f"\n{'='*60}\n🏪 STORE_BRAND_WORKFLOW: Processing store/brand question\n{'='*60}") or state)
    graph.add_node("unrelated_workflow", lambda state: print(f"\n{'='*60}\n🤷 UNRELATED_WORKFLOW: Processing unrelated query\n{'='*60}") or state)
    
    # Add conditional routing for error handling and intent workflows
    def get_next_hop(state):
        # Check for errors first
        if state.error:
            return "error"
        
        intent = state.intent_decision.intent
        if intent == UserIntent.PRODUCT_RECOMMENDATION:
            return intent
        elif intent == UserIntent.PRODUCT_INQUIRY:
            return "product_inquiry_workflow"
        elif intent == UserIntent.STORE_BRAND_QUESTION:
            return "store_brand_workflow"
        elif intent == UserIntent.UNRELATED:
            return "unrelated_workflow"
        
    
    def has_error(state):
        return state.error != None

    # Add edges
    graph.set_entry_point("classify_intent")
    
    # Add conditional edges from classify_intent
    graph.add_conditional_edges(
        "classify_intent",
        get_next_hop,
        {
            "error": "error",
            UserIntent.PRODUCT_RECOMMENDATION: "get_product_filters_node",
            "product_inquiry_workflow": "product_inquiry_workflow", 
            "store_brand_workflow": "store_brand_workflow",
            "unrelated_workflow": "unrelated_workflow"
        }
    )

    # Add edges from workflow nodes to END
    graph.add_conditional_edges("get_product_filters_node", has_error, {True: "error", False: "fetch_candidate_products_node"})
    graph.add_conditional_edges("fetch_candidate_products_node", has_error, {True: "error",False: END})
    graph.add_edge("product_inquiry_workflow", END)
    graph.add_edge("store_brand_workflow", END)
    graph.add_edge("unrelated_workflow", END)
    graph.add_edge("error", END)
    
    _compiled_graph = graph.compile()
    return _compiled_graph