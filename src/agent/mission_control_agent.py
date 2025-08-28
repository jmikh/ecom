"""
Mission Control Agent - Routes user queries to appropriate workflows
Acts as the central decision-maker for determining user intent and routing
"""

from typing import List, Dict, Any, Optional, Sequence
from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain.prompts import SystemMessagePromptTemplate
try:
    from .config import config
    from .memory import ConversationMemory, SessionManager
    from .compose_main_graph import compose_main_graph
    from ..database.database_pool import get_database
except ImportError:
    # For standalone execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent.config import config
    from agent.memory import ConversationMemory, SessionManager
    from agent.compose_main_graph import compose_main_graph


class UserIntent(str, Enum):
    """Enumeration of possible user intents"""
    PRODUCT_RECOMMENDATION = "product_recommendation"
    PRODUCT_INQUIRY = "product_inquiry"
    STORE_BRAND_QUESTION = "store_brand_question"
    UNRELATED = "unrelated"


class IntentDecision(BaseModel):
    """Structured response for intent classification"""
    intent: UserIntent = Field(
        description="The classified intent of the user's message"
    )
    confidence: float = Field(
        ge=0.0, 
        le=1.0,
        description="Confidence score of the classification (0-1)"
    )
    context: str = Field(
        description="Explanation of why this classification was made"
    )
    key_indicators: List[str] = Field(
        default_factory=list,
        description="Key phrases or indicators that led to this decision"
    )
    suggested_action: str = Field(
        description="Suggested next action based on the intent"
    )


class GraphState(BaseModel):
    """State schema for the agent graph - main entry point for all workflows"""
    # Core identifiers - required fields first
    session_id: str = Field(
        description="Unique session identifier for conversation continuity"
    )
    tenant_id: str = Field(
        description="Tenant ID for multi-tenant isolation"
    )
    
    # Note: Database connection removed - using connection pool from database_pool.py
    # The pool automatically manages connections, tenant isolation, and safety settings
    
    # Core conversation state - ONLY user ↔ assistant exchanges
    chat_messages: Sequence[BaseMessage] = Field(
        default_factory=list,
        description="Clean conversation history: only HumanMessage ↔ AIMessage exchanges between user and assistant"
    )
    
    # Internal processing state - separate from conversation
    internal_messages: Sequence[BaseMessage] = Field(
        default_factory=list,
        description="Internal processing messages: SystemMessage, ToolMessage, LLM interactions, etc. Used for workflow processing but NOT saved to conversation history"
    )
    
    # Intent classification results
    intent_decision: Optional[IntentDecision] = Field(
        default=None,
        description="Complete intent classification decision with intent, confidence, context, etc."
    )
    
    # Shared data needed across nodes
    tenant_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tenant information (store name, description) for context"
    )
    llm_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LLM configuration for intent classification"
    )
    session_manager_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Session management configuration"
    )
    
    # Workflow routing
    active_workflow: Optional[str] = Field(
        default=None,
        description="Currently active workflow (product_search, product_details, store_info, etc.)"
    )
    workflow_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parameters for the active workflow"
    )
    
    # Product-related state
    current_products: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Products being discussed or returned from search"
    )
    search_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Context from product searches (filters, semantic queries, etc.)"
    )
    
    # Execution state
    next_action: Optional[str] = Field(
        default=None,
        description="Next action to take in the current workflow"
    )
    tool_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for tool execution"
    )
    
    # Response state
    final_answer: Optional[str] = Field(
        default=None,
        description="Final response to user"
    )
    needs_clarification: bool = Field(
        default=False,
        description="Whether the agent needs clarification from the user"
    )
    
    # State management
    conversation_complete: bool = Field(
        default=False,
        description="Whether the current conversation turn is complete"
    )
    
    class Config:
        arbitrary_types_allowed = True



# Global node functions for the graph workflow
def retrieve_context_node(state: GraphState) -> GraphState:
    """Node: Retrieve conversation context and build message history"""
    print(f"🔍 MISSION_CONTROL: Retrieving context for global node")
    
    # Get the current user message from chat_messages
    current_message = ""
    if state.chat_messages:
        # Get the last human message
        for msg in reversed(state.chat_messages):
            if isinstance(msg, HumanMessage):
                current_message = msg.content
                break
    
    # For now, we'll assume the session and memory management 
    # will be handled externally or passed through state
    print(f"🔍 MISSION_CONTROL: Processing message: '{current_message[:50]}...'")
    
    return state


def classify_intent_node(state: GraphState) -> GraphState:
    """Node: Classify the intent of the user message"""
    print(f"🧠 MISSION_CONTROL: Classifying intent (global node)")
    
    # Create LLM instance within the node
    llm = ChatOpenAI(
        model=config.openai_model,
        temperature=0.1,  # Low temperature for consistent classification
        openai_api_key=config.openai_api_key
    ).with_structured_output(IntentDecision)
    
    # Get tenant info from state or fetch from database using connection pool
    if not state.tenant_info:
        # Fetch tenant info from database using connection pool
        try:
            db = get_database()
            result = db.run_read(
                sql="SELECT name, description FROM tenants WHERE tenant_id = %s",
                params=(state.tenant_id,),
                tenant_id=state.tenant_id
            )
            
            if result:
                # run_read returns a list, get first result
                tenant_data = result[0]
                state.tenant_info = {
                    "store_name": tenant_data['name'],
                    "store_description": tenant_data['description'] or "E-commerce store"
                }
            else:
                state.tenant_info = {
                    "store_name": "Store",
                    "store_description": "E-commerce store"
                }
        except Exception as e:
            print(f"Warning: Could not fetch tenant info: {e}")
            state.tenant_info = {
                "store_name": "Store", 
                "store_description": "E-commerce store"
            }
    
    # Get the current user message from chat_messages
    current_message = ""
    if state.chat_messages:
        # Get the last human message
        for msg in reversed(state.chat_messages):
            if isinstance(msg, HumanMessage):
                current_message = msg.content
                break
    
    if not current_message:
        # Fallback decision if no message found
        decision = IntentDecision(
            intent=UserIntent.UNRELATED,
            confidence=0.0,
            context="No user message found for classification",
            key_indicators=[],
            suggested_action="Request user input"
        )
    else:
        # Create system prompt template
        system_prompt_template = SystemMessagePromptTemplate.from_template(
            """You are a mission control agent for an e-commerce assistant. 
Your role is to analyze user messages and determine their intent to route them to the appropriate workflow.

STORE CONTEXT:
Store Name: {store_name}
Store Description: {store_description}

This context helps you understand what kind of store you're assisting with, but your primary job is intent classification.

Classify user messages into one of these categories:

1. **product_recommendation**: User wants suggestions, recommendations, or help finding products
   - Examples: "Show me running shoes", "I need something for camping", "What do you have in blue?", "Find me gifts under $50"
   - Key indicators: "show", "find", "recommend", "suggest", "looking for", "need", "want", price ranges, product attributes

2. **product_inquiry**: User is asking about specific products they already know about
   - Examples: "Tell me more about product X", "What colors does this come in?", "Is this item in stock?", "How much is the backpack?"
   - Key indicators: specific product names, "this item", "that product", questions about availability/details

3. **store_brand_question**: User is asking about the store, brand, policies, or general information
   - Examples: "What's your return policy?", "Where are you located?", "Tell me about your brand", "Do you ship internationally?"
   - Key indicators: "policy", "brand", "store", "shipping", "returns", "about us", company-related terms

4. **unrelated**: User's message is not related to shopping or the store
   - Examples: "What's the weather?", "Tell me a joke", "How do I cook pasta?", "What's 2+2?"
   - Key indicators: topics unrelated to commerce, general knowledge questions, personal conversations

Analyze the MOST RECENT user message in context of the conversation history.
Focus primarily on the latest message but use history to understand context.
Provide high confidence (0.8-1.0) when intent is clear, medium (0.5-0.7) when somewhat ambiguous, and low (0.0-0.4) when very unclear.

Be accurate and consistent in your classification."""
        )
        
        # Build the message list with contextualized system prompt
        system_message = system_prompt_template.format(
            store_name=state.tenant_info["store_name"],
            store_description=state.tenant_info["store_description"]
        )
        messages = [system_message]
        
        # Add conversation history from chat_messages (excluding current message)
        for msg in state.chat_messages[:-1]:
            if isinstance(msg, (HumanMessage, AIMessage)):
                messages.append(msg)
        
        # Add the current message with emphasis
        classification_request = f"""
Analyze this user message and classify its intent:

USER MESSAGE: "{current_message}"

Consider the conversation history above for context. Messages like "what about this" or "tell me more" 
refer to previous conversation elements.

Provide your classification with:
- The intent category
- A confidence score (0-1)
- Context explaining your reasoning
- Key indicators that led to this decision
- A suggested action for handling this intent
"""
        messages.append(HumanMessage(content=classification_request))
        
        # Add all LLM request messages to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + messages
        
        # Get structured response
        try:
            decision = llm.invoke(messages)
            
            # Add LLM response to internal_messages for debugging flow
            state.internal_messages = list(state.internal_messages) + [
                AIMessage(content=f"MISSION_CONTROL_CLASSIFICATION_RESPONSE: Intent={decision.intent}, Confidence={decision.confidence}")
            ]
            
        except Exception as e:
            # Fallback decision if classification fails
            decision = IntentDecision(
                intent=UserIntent.UNRELATED,
                confidence=0.0,
                context=f"Classification failed: {str(e)}",
                key_indicators=[],
                suggested_action="Request clarification from user"
            )
    
    # Store classification results in state
    state.intent_decision = decision
    
    print(f"🎯 MISSION_CONTROL: Classified as {decision.intent} (confidence: {decision.confidence})")
    return state


def route_workflow_node(state: GraphState) -> GraphState:
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


# Global utility functions
# create_db_connection removed - now using connection pool from database_pool.py
# The pool automatically manages connections, tenant isolation, and safety settings


def retrieve_context(current_message: str, session_id: str, tenant_id: str) -> List[BaseMessage]:
    """Retrieve conversation context and build message history"""
    print(f"🔍 MISSION_CONTROL: Retrieving context for session {session_id}")
    
    # Initialize session management
    memory = ConversationMemory(session_id, tenant_id)
    session_manager = SessionManager()
    
    # Get conversation history
    history = memory.get_conversation_history()
    
    # Check if session exists
    session_data = session_manager.get_session_data(session_id, tenant_id)
    
    # Create session if it doesn't exist
    if not session_data:
        session_manager.create_session(session_id, tenant_id)
    
    # Build message list with history
    messages = []
    
    # Add recent history for context (last 5 exchanges)
    for item in history[-5:]:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
    
    # Add current message
    messages.append(HumanMessage(content=current_message))
    
    print(f"🔍 MISSION_CONTROL: Retrieved {len(history)} history items, built {len(messages)} messages")
    return messages


def get_workflow_recommendation(decision: IntentDecision) -> Dict[str, Any]:
    """Get detailed workflow recommendation based on intent decision"""
    workflow_map = {
        UserIntent.PRODUCT_RECOMMENDATION: {
            "workflow": "product_search",
            "agent": "ProductAgent",
            "tools": ["search_products", "semantic_search"],
            "description": "Use product search and recommendation capabilities",
            "parameters": {
                "use_semantic_search": True,
                "include_filters": True,
                "max_results": 10
            }
        },
        UserIntent.PRODUCT_INQUIRY: {
            "workflow": "product_details",
            "agent": "ProductAgent", 
            "tools": ["get_product_details", "check_inventory"],
            "description": "Retrieve specific product information",
            "parameters": {
                "detailed_info": True,
                "include_variants": True,
                "include_availability": True
            }
        },
        UserIntent.STORE_BRAND_QUESTION: {
            "workflow": "store_info",
            "agent": "StoreInfoAgent",
            "tools": ["get_store_info", "get_policies"],
            "description": "Provide store and brand information",
            "parameters": {
                "info_type": "general"
            }
        },
        UserIntent.UNRELATED: {
            "workflow": "polite_redirect",
            "agent": "GeneralAgent",
            "tools": [],
            "description": "Politely redirect to shopping assistance",
            "parameters": {
                "response_type": "redirect",
                "suggest_alternatives": True
            }
        }
    }
    
    workflow = workflow_map[decision.intent].copy()
    workflow["confidence"] = decision.confidence
    workflow["reasoning"] = decision.context
    workflow["decision"] = decision.model_dump()
    
    return workflow


async def process_user_query(
    user_message: str, 
    tenant_id: str, 
    session_id: Optional[str] = None,
    return_workflow: bool = True
) -> Dict[str, Any]:
    """
    Process a user query through the mission control workflow
    
    Args:
        user_message: The user's message
        tenant_id: Tenant ID for multi-tenant isolation  
        session_id: Optional session ID for conversation continuity
        return_workflow: Whether to include workflow recommendations
        
    Returns:
        Complete routing decision with classification and workflow details
    """
    import uuid
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Get context messages (conversation history + current message)
    chat_messages = retrieve_context(user_message, session_id, tenant_id)
    
    # Create minimal initial GraphState with required fields only
    # No db_connection needed - using connection pool from database_pool.py
    initial_state = GraphState(
        session_id=session_id,
        tenant_id=tenant_id,
        chat_messages=chat_messages,
        # All other fields will use their defaults and be populated by nodes
    )
    
    # Build and run the graph
    graph = compose_main_graph()
    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": 10
    }
    
    # No need to manage connection lifecycle - pool handles it automatically
    final_state = await graph.ainvoke(initial_state, config)
    
    # Extract intent decision from final state
    intent_decision = final_state.get('intent_decision')
    
    # Build response
    response = {
        "timestamp": datetime.now().isoformat(),
        "query": user_message,
        "decision": intent_decision.model_dump() if intent_decision else None,
        "tenant_id": tenant_id,
        "session_id": session_id
    }
    
    # Add workflow recommendation if requested
    if return_workflow and intent_decision:
        response["workflow"] = get_workflow_recommendation(intent_decision)
    
    return response


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    import atexit
    from ..database.database_pool import get_database
    
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
                "Tell me more about the blue backpack",
                "What's your return policy?",
                "How's the weather today?",
                "I need camping gear for a weekend trip",
                "Is the Nike Air Max in stock?",
                "Where is your store located?",
                "Can you tell me a joke?"
            ]
            
            print("Mission Control - Intent Classification Test (Global Functions)\n")
            print("=" * 60)
            
            # Test just the first query
            query = test_queries[0]
            print(f"\nTesting: '{query}'")
            try:
                result = await process_user_query(query, tenant_id)
                decision = result["decision"]
                
                if decision:
                    print(f"Intent: {decision['intent']}")
                    print(f"Confidence: {decision['confidence']:.2f}")
                    print(f"Context: {decision['context']}")
                    print(f"Suggested Action: {decision['suggested_action']}")
                    
                    if result.get("workflow"):
                        workflow = result["workflow"]
                        print(f"Workflow: {workflow['workflow']}")
                        print(f"Agent: {workflow['agent']}")
                else:
                    print("No decision returned")
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