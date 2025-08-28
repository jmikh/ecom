"""
Main Graph Composition for Mission Control Agent
Builds the LangGraph workflow that handles intent classification and routing
"""

from langgraph.graph import StateGraph, END


def compose_main_graph() -> StateGraph:
    """
    Build the main LangGraph workflow for mission control using global node functions
        
    Returns:
        Compiled StateGraph for mission control workflow
    """
    # Define the graph - get GraphState from the mission control agent module
    from . import mission_control_agent
    workflow = StateGraph(mission_control_agent.GraphState)
    
    # Add nodes - use global node functions
    workflow.add_node("retrieve_context", mission_control_agent.retrieve_context_node)
    workflow.add_node("classify_intent", mission_control_agent.classify_intent_node)
    workflow.add_node("route_workflow", mission_control_agent.route_workflow_node)
    
    # Add edges
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "classify_intent")
    workflow.add_edge("classify_intent", "route_workflow")
    workflow.add_edge("route_workflow", END)
    
    # Compile without checkpointer for now (db_connection not serializable)
    graph = workflow.compile()
    
    return graph