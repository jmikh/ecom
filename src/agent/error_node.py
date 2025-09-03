
from src.agent.graph_state import GraphState
from src.shared.schemas import ChatServerResponse

# Global node functions for the graph workflow
def error_node(state: GraphState) -> GraphState:
    """Node: Handle errors and provide fallback response"""
    print(f"\n{'='*60}")
    print(f"❌ ERROR_NODE: Handling error")
    print(f"Error: {state.error}")
    print(f"{'='*60}")
    
    # Set error response using ChatServerResponse
    state.chat_server_response = ChatServerResponse(
        message="I'm sorry, but I'm experiencing technical difficulties. Please try again later."
    )
    
    return state
