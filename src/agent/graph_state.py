from typing import List, Dict, Any, Optional, Sequence
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from src.shared.schemas import ChatServerResponse



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
    
    workflow_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parameters for the active workflow"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="error string if an error was encountered"
    )
    
    # Response state
    chat_server_response: Optional[ChatServerResponse] = Field(
        default=None,
        description="Structured response to send to the user"
    )