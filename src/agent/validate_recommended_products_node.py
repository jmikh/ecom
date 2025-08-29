from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langsmith import traceable

from src.agent.graph_state import GraphState
from src.agent.config import config


class ProductValidation(BaseModel):
    product_id: int = Field(description="The product ID from the database")
    relevance_score: float = Field(
        ge=0.0, 
        le=1.0, 
        description="Relevance score from 0.0 to 1.0 based on how well it matches the user's request"
    )
    fits_criteria: bool = Field(description="True if the product fits the user's criteria, False otherwise")
    reason: str = Field(
        description="Short sentence explaining why this product was selected or why it doesn't fit but is still shown"
    )


class ValidatedProductsResponse(BaseModel):
    validated_products: List[ProductValidation] = Field(
        description="List of products ordered by relevance with validation details"
    )
    overall_summary: str = Field(
        description="Brief summary of the product selection and recommendations"
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
        ).with_structured_output(ValidatedProductsResponse)
        
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
        
        # Store validation results in final_answer
        state.final_answer = validation_response.model_dump_json(indent=2)
        
        state.internal_messages.append(AIMessage(content=f"Validation complete: {len(validation_response.validated_products)} products ranked"))
        
        print(f"✅ Validated {len(validation_response.validated_products)} products")
        print(f"📊 Overall summary: {validation_response.overall_summary}")
        
    except Exception as e:
        print(f"❌ Error validating products: {e}")
        state.error = f"Product validation failed: {str(e)}"
        
    return state