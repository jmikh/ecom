from typing import List, Dict, Any, Optional, Sequence
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage



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

    store_context_str: Optional[str] = Field(
        default="",
        description="The chat messages above but transformed into a string format to be easily fed into LLMs"
    )

    # Core conversation state - ONLY user ↔ assistant exchanges
    chat_messages: Sequence[BaseMessage] = Field(
        default_factory=list,
        description="Clean conversation history: only HumanMessage ↔ AIMessage exchanges between user and assistant"
    )

    chat_messages_str: Optional[str] = Field(
        default="",
        description="The chat messages above but transformed into a string format to be easily fed into LLMs"
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
    

    
    error: Optional[str] = Field(
        default=None,
        description="error string if an error was encountered"
    )
    tool_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for tool execution"
    )
    
    # Product filter extraction
    products_filter: Optional[Any] = Field(
        default=None,
        description="Extracted product search filters from conversation"
    )
    
    # Product search results
    finalist_products: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Final list of products returned from search"
    )
    
    # Response state
    final_answer: Optional[str] = Field(
        default=None,
        description="Final response to user"
    )