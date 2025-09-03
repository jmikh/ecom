from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langsmith import traceable

from src.agent.graph_state import GraphState
from src.agent.config import config
from src.shared.schemas import ProductCard, ChatServerResponse
from src.agent.common import get_products_details_by_ids, fetch_product_cards_by_ids


class LLMProductValidation(BaseModel):
    """LLM's validation of products with user-friendly response"""
    product_ids: List[int] = Field(
        description="List of product IDs ordered by relevance (empty list if no products match)"
    )
    user_response: str = Field(
        description="Friendly response to the user explaining why they would like these products, or if no exact matches, explain what alternatives are shown and why"
    )


def formulate_response_node(state: GraphState) -> GraphState:
    """Node: Fetch product details and formulate response with most relevant products"""
    print(f"\n{'='*60}")
    print(f"📝 FORMULATE_RESPONSE_NODE: Creating response with relevant products")
    print(f"{'='*60}")
    
    try:
        # Get product IDs from search results
        search_results = state.workflow_params.get("search_products", [])
        if not search_results:
            raise ValueError("No products found from search")
        
        # Extract just the IDs
        product_ids = [p['id'] for p in search_results]
        print(f"📦 Fetching details for {len(product_ids)} products...")
        
        # Fetch full product details using common utility
        products_with_details = get_products_details_by_ids(product_ids, state.tenant_id)
        
        # Create LLM instance with structured output
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.1,  # Low temperature for consistent validation
            openai_api_key=config.openai_api_key
        ).with_structured_output(LLMProductValidation)
        
        # Format products for LLM analysis
        import json
        products_text = json.dumps(products_with_details, indent=2, default=str)
        
        # Create system message
        system_message = SystemMessage(content="""
You are a friendly e-commerce assistant helping customers find products they'll love.
Your job is to review candidate products and craft a helpful response to the user.

Instructions:
1. Select the most relevant products based on the user's request (ordered by relevance)
2. Write a conversational response that:
   - If products match well: Explain why the user would like these specific products (features, benefits, value)
   - If no exact matches: Acknowledge this honestly and explain what alternatives you're showing and why they might still be helpful
   - Be specific about product features that match their needs
   - Be honest if products don't perfectly match their criteria
   - Keep the tone friendly and helpful

Remember: Users appreciate honesty. If you couldn't find exactly what they asked for, say so and explain what you found instead.
        """)
        
        # Create user message with conversation history and products
        user_message = HumanMessage(content=f"""
Customer request:
{state.chat_messages_str}

Available products from our catalog:
{products_text}

Please select the best products for this customer and write a helpful response explaining your recommendations.
If these products don't perfectly match what they asked for, be honest about it and explain why these are the best alternatives available.
        """)
        
        messages = [system_message, user_message]
        
        # Get structured response
        validation_response = llm.invoke(messages)
        
        # Fetch ProductCard objects for the LLM's selected product IDs
        # This function handles all conversions and None values properly
        product_cards = fetch_product_cards_by_ids(
            validation_response.product_ids, 
            state.tenant_id
        )
        
        # Create the final structured response with single message field
        state.chat_server_response = ChatServerResponse(
            products=product_cards if product_cards else None,
            message=validation_response.user_response
        )
        
        print(f"✅ Selected {len(product_cards)} products from {len(products_with_details)} candidates")
        print(f"💬 Response: {validation_response.user_response[:100]}...")
        
    except Exception as e:
        print(f"❌ Error validating products: {e}")
        state.error = f"Product validation failed: {str(e)}"
        
    return state