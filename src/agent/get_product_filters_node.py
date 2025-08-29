
from typing import Optional, Dict, Union, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langsmith import traceable

from src.agent.graph_state import GraphState
from src.agent.config import config

class SqlFilter(BaseModel):
    product_type: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    has_discount: Optional[bool] = None

class ProductsFilter(BaseModel):
    sql_filters: SqlFilter = Field(
        default_factory=SqlFilter,
        description="""Structured filters for product search (product_type, min_price, max_price, has_discount).
        Example: SqlFilter(product_type="Shoes", max_price=100.0, has_discount=True)"""
    )

    semantic_query: Optional[str] = Field(
        default=None,
        description="Free-text semantic query to match against embeddings. Example: 'comfortable running shoes for marathon'"
    )

    k: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Number of results to return (default 5, max 25), don't change unless the user clearly specifies a number"
    )
    
# Global node functions for the graph workflow
def get_product_filters_node(state: GraphState) -> GraphState:
    """Node: Extract product filters from conversation history"""
    print(f"\n{'='*60}")
    print(f"🎯 GET_PRODUCT_FILTERS_NODE: Extracting filters from conversation")
    print(f"{'='*60}")
    
    try:
        # Create LLM instance with structured output using function calling for flexibility
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.1,  # Low temperature for consistent filter extraction
            openai_api_key=config.openai_api_key
        ).with_structured_output(ProductsFilter)
        
        # Create system message
        system_message = SystemMessage(content="""
You are a product filter extraction agent for an e-commerce store.
Your job is to analyze conversation history and extract relevant product search filters.

Extract filters for:
- product_type: Category like "Shoes", "Clothing", "Electronics", etc.
- min_price/max_price: Price range if mentioned
- vendor: Brand names like "Nike", "Apple", etc.
- has_discount: If user wants discounted items
- tags: Keywords like "waterproof", "wireless", etc.

Also create a semantic_query that captures the essence of what the user is looking for.
Set k (number of results) only if user specifies a specific number, otherwise keep default of 5.
        """)
        
        # Create user message with conversation history
        user_message = HumanMessage(content=f"""
Based on this conversation history, extract product search filters:

{state.chat_messages_str}

Focus on the most recent user message but use the full context to understand what they're looking for.
        """)
        
        messages = [system_message, user_message]
        state.internal_messages.extend(messages)
        
        # Get structured response
        state.products_filter = llm.invoke(messages)

        state.internal_messages.append(AIMessage(content=f"Extracted filters: {state.products_filter.model_dump()}"))
        
        print(f"🎯 Extracted filters: {state.products_filter.model_dump()}")
        
    except Exception as e:
        print(f"❌ Error extracting filters: {e}")
        state.error = f"Filter extraction failed: {str(e)}"
        
    return state

