from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langsmith import traceable

from src.agent.graph_state import GraphState
from src.agent.config import config
from src.shared.schemas import ProductCard, ProductRecommendationResponse


class LLMProductValidation(BaseModel):
    """LLM's validation of products - only IDs and reasoning"""
    product_ids: List[int] = Field(
        description="List of product IDs ordered by relevance"
    )
    reasoning: str = Field(
        description="Overall explanation of why these products were recommended"
    )


def validate_recommended_products_node(state: GraphState) -> GraphState:
    """Node: Validate and rank candidate products using LLM"""
    print(f"\n{'='*60}")
    print(f"✅ VALIDATE_RECOMMENDED_PRODUCTS_NODE: Validating product relevance")
    print(f"{'='*60}")
    
    try:
        if not state.finalist_products:
            raise ValueError("No finalist products found to validate")
        
        # Create LLM instance with structured output
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.1,  # Low temperature for consistent validation
            openai_api_key=config.openai_api_key
        ).with_structured_output(LLMProductValidation)
        
        # Format products for LLM analysis
        import json
        products_text = json.dumps(state.finalist_products, indent=2, default=str)
        
        # Create system message
        system_message = SystemMessage(content="""
You are a product recommendation validator for an e-commerce store.
Your job is to analyze candidate products and determine how well they match the user's request.

For each product, evaluate:
1. Relevance score (0.0-1.0) - How well does it match what the user is looking for?
2. Fits criteria (true/false) - Does it meet the specific requirements mentioned?
3. Reason - Brief explanation of why it was selected or why it's shown despite not being perfect

Order the products by relevance score (highest first).
Provide an overall summary of the recommendations.
        """)
        
        # Create user message with conversation history and products
        user_message = HumanMessage(content=f"""
Based on this conversation history:
{state.chat_messages_str}

Validate and rank these candidate products:
{products_text}

Consider the user's specific requirements (price range, product type, features mentioned) and rank by relevance.
        """)
        
        messages = [system_message, user_message]
        state.internal_messages.extend(messages)
        
        # Get structured response
        validation_response = llm.invoke(messages)
        
        # Build ProductCard objects from finalist products matching the LLM's selected IDs
        product_cards = []
        products_by_id = {p['id']: p for p in state.finalist_products}
        
        for product_id in validation_response.product_ids:
            if product_id in products_by_id:
                product = products_by_id[product_id]
                card = ProductCard(
                    id=product['id'],
                    name=product.get('title', ''),
                    vendor=product.get('vendor', ''),
                    image_url=product.get('image_url'),
                    price_min=float(product.get('min_price', 0)),
                    price_max=float(product.get('max_price', 0)),
                    has_discount=product.get('has_discount', False)
                )
                product_cards.append(card)
        
        # Create the final structured response
        recommendation_response = ProductRecommendationResponse(
            products=product_cards,
            message=validation_response.reasoning
        )
        
        # Store structured response as JSON string in final_answer
        state.final_answer = recommendation_response.model_dump_json(indent=2)
        
        state.internal_messages.append(AIMessage(content=f"Validation complete: {len(product_cards)} products selected"))
        
        print(f"✅ Selected {len(product_cards)} products from {len(state.finalist_products)} candidates")
        print(f"📊 Reasoning: {validation_response.reasoning}")
        
    except Exception as e:
        print(f"❌ Error validating products: {e}")
        state.error = f"Product validation failed: {str(e)}"
        
    return state