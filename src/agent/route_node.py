    
from src.agent.graph_state import GraphState, UserIntent

def route_node(state: GraphState) -> GraphState:
    """Node: Route to appropriate workflow based on classified intent"""
    intent = state.intent_decision.intent if state.intent_decision else "UNKNOWN"
    print(f"🚀 MISSION_CONTROL: Routing to workflow for intent {intent}")
    
    if state.intent_decision:
        # Basic workflow mapping - this could be enhanced
        workflow_map = {
            UserIntent.PRODUCT_RECOMMENDATION: {
                "workflow": "product_search",
                "agent": "ProductAgent",
                "parameters": {"use_semantic_search": True}
            },
            UserIntent.PRODUCT_INQUIRY: {
                "workflow": "product_details", 
                "agent": "ProductAgent",
                "parameters": {"detailed_info": True}
            },
            UserIntent.STORE_BRAND_QUESTION: {
                "workflow": "store_info",
                "agent": "StoreInfoAgent", 
                "parameters": {"info_type": "general"}
            },
            UserIntent.UNRELATED: {
                "workflow": "polite_redirect",
                "agent": "GeneralAgent",
                "parameters": {"response_type": "redirect"}
            }
        }
        
        workflow = workflow_map.get(state.intent_decision.intent, workflow_map[UserIntent.UNRELATED])
        state.active_workflow = workflow["workflow"]
        state.workflow_params = workflow["parameters"]
        
        print(f"🎯 MISSION_CONTROL: Routed to {workflow['workflow']} workflow")
    
    return state
