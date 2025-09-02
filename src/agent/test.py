"""
Main entry point for the Mission Control Agent
"""

import uuid
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from src.agent.classify_intent_node import GraphState
from src.agent.main_graph import get_main_graph
from src.database import ConversationMemory, get_database


async def process_user_query(
    user_message: str, 
    tenant_id: str, 
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a user query through the mission control workflow
    
    Args:
        user_message: The user's message
        tenant_id: Tenant ID for multi-tenant isolation  
        session_id: Optional session ID for conversation continuity
        
    Returns:
        Complete routing decision with classification and workflow details
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    memory = ConversationMemory(session_id, tenant_id)
    memory.add_message(user_message, "user")

    initial_state = GraphState(
        session_id=session_id,
        tenant_id=tenant_id,
    )
    # Get compiled graph and run
    graph = get_main_graph()
    
    final_state_dict = await graph.ainvoke(initial_state)
    
    # Reconstruct GraphState from dictionary
    final_state = GraphState.model_validate(final_state_dict)
    
    # Extract intent decision from final state
    # intent_decision = final_state.intent_decision
    # messages = list(final_state.internal_messages)
    # print(f"Found {len(messages)} internal messages")
    # for message in messages:
    #     print(str(message) + "\n")
    
    print("FINAL ANSWER:\n")
    return final_state.final_answer


# Example usage and testing
if __name__ == "__main__":
    # Global variable for database instance cleanup
    _db_instance = None
    
    def main():
        # Initialize database connection pool
        print("🚀 Starting Mission Control Agent...")
        try:
            global _db_instance
            _db_instance = get_database()
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Failed to initialize database - continuing anyway: {e}")
            _db_instance = None
        
        async def test_mission_control():
            # Test the new global function approach
            tenant_id = "6b028cbb-512d-4538-a3b1-71bc40f49ed1"
            
            # Test queries
            test_queries = [
                "Show me some running shoes under $100",
            ]
            
            print("Mission Control - Intent Classification Test (Global Functions)\n")
            print("=" * 60)
            
            # Test just the first query
            query = test_queries[0]
            print(f"\nTesting: '{query}'")
            try:
                result = await process_user_query(query, tenant_id)
                print(result)
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Run the async test
        try:
            asyncio.run(test_mission_control())
        finally:
            # Explicit cleanup
            if _db_instance:
                _db_instance.close()
    
    main()