"""
Mission Control Agent - Routes user queries to appropriate workflows
Acts as the central decision-maker for determining user intent and routing
"""

from typing import List, Dict, Any, Optional, Sequence
from datetime import datetime
from enum import Enum
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain.prompts import SystemMessagePromptTemplate
from langsmith import traceable
import asyncio

from src.agent.config import config
from src.database import get_database
from src.database.message_store import ConversationMemory
from src.agent.graph_state import GraphState, UserIntent, IntentDecision


@traceable(name="fetch_tenant_info")
def fetch_tenant_info(tenant_id: str) -> Dict[str, str]:
    """Fetch tenant information from database"""
    db = get_database()
    result = db.run_read(
        sql="SELECT name, description FROM tenants WHERE tenant_id = %s",
        params=(tenant_id,),
        tenant_id=tenant_id
    )
    
    if not result:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    tenant_data = result[0]
    return {
        "store_name": tenant_data['name'],
        "store_description": tenant_data['description'] or "E-commerce store"
    }


@traceable(name="fetch_chat_history")
def fetch_chat_history(session_id: str, tenant_id: str) -> List[BaseMessage]:
    """Retrieve chat history between assistant and user"""
    memory = ConversationMemory(session_id, tenant_id)
    history = memory.get_messages(5)
    
    messages = []
    for item in history:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            # Use structured_data if available (contains message + products), otherwise just content
            if item.get("structured_data"):
                import json
                messages.append(AIMessage(content=json.dumps(item["structured_data"])))
            else:
                messages.append(AIMessage(content=item["content"]))
    
    return messages

_system_prompt_template = system_prompt_template = SystemMessagePromptTemplate.from_template(
            """You are an intent classifier agent for an e-commerce assistant. 
Your role is to analyze user messages and determine their intent to route them to the appropriate workflow.

{store_context}

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

async def classify_intent_node(state: GraphState) -> GraphState:
    """Node: Classify the intent of the user message"""
    print(f"\n{'='*60}")
    print(f"🧠 CLASSIFY_INTENT_NODE: Starting intent classification")
    print(f"{'='*60}")
    
    try:
        # Call both functions asynchronously
        tenant_info_task = asyncio.to_thread(fetch_tenant_info, state.tenant_id)
        chat_history_task = asyncio.to_thread(fetch_chat_history, state.session_id, state.tenant_id)
        
        # Wait for both results
        state.tenant_info, state.chat_messages = await asyncio.gather(tenant_info_task, chat_history_task)
        
        # Check that the last message is from the user
        if not state.chat_messages or not isinstance(state.chat_messages[-1], HumanMessage):
            raise ValueError("Last message in chat history must be from user")
        
            # Build conversation history string
        for msg in state.chat_messages:
            if isinstance(msg, HumanMessage):
                state.chat_messages_str  += f"USER: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                state.chat_messages_str  += f"CHATBOT: {msg.content}\n"

        state.store_context_str = f"""STORE CONTEXT:
                Store Name: {state.tenant_info["store_name"]}
                Store Description: {state.tenant_info["store_description"]}"""
        
    except Exception as e:
        print(f"❌ Error in classify_intent_node: {e}")
        state.error = str(e)
        return state
    
    # Create LLM instance within the node
    llm = ChatOpenAI(
        model=config.openai_model,
        temperature=0.1,  # Low temperature for consistent classification
        openai_api_key=config.openai_api_key
    ).with_structured_output(IntentDecision)
    
    global _system_prompt_template
    system_message = _system_prompt_template.format(store_context=state.store_context_str)
    classification_message = HumanMessage(f"Classify the intent of this chat history: {state.chat_messages_str}")
    
    messages = [system_message, classification_message]
    
    try:
        state.intent_decision = llm.invoke(messages)
        print(f"🎯 Classify Intent: {state.intent_decision}")
        
    except Exception as e:
        state.error = str(e)
    
    return state
    