"""
Answer Product Question Node
Generates detailed answers about a specific product based on user questions
"""

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.graph_state import GraphState
from src.agent.config import config
from src.shared.schemas import ChatServerResponse
from src.agent.common import fetch_product_cards_by_ids


class ProductAnswer(BaseModel):
    """LLM's answer about a specific product"""
    answer: str = Field(
        description="Detailed answer to the user's question about the product"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the answer"
    )


def answer_product_question_node(state: GraphState) -> GraphState:
    """
    Third node: Generate answer about the specific product
    """
    print(f"\n{'='*60}")
    print(f"💬 ANSWER_PRODUCT_QUESTION_NODE: Generating product answer")
    print(f"{'='*60}")
    
    try:
        # Get product(s) - could be single or multiple
        single_product = state.workflow_params.get('selected_product')
        multiple_products = state.workflow_params.get('selected_products', [])
        
        products = [single_product] if single_product else multiple_products
        if not products:
            raise ValueError("No products found to answer about")
        
        # Create LLM for answering
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.3,
            openai_api_key=config.openai_api_key
        ).with_structured_output(ProductAnswer)
        
        # Format product details (handle single or multiple)
        if len(products) == 1:
            product = products[0]
            product_details = f"""
Product Information (ONLY use the data provided below):
- Name: {product['title']}
- Brand/Vendor: {product.get('vendor') or 'Not specified'}
- Type: {product.get('product_type') or 'Not specified'}
- Price Range: ${product['min_price']:.2f} - ${product['max_price']:.2f}
- On Sale: {'Yes' if product.get('has_discount') else 'No'}
- Description: {product.get('body_html') or 'Not available'}
- Tags: {', '.join(product['tags']) if product.get('tags') else 'Not available'}
- Options: {product.get('options') or 'Not available'}

Note: If any field shows "Not available" or "Not specified", that information is not in our database.
        """
        else:
            # Multiple products
            product_details = "Products being asked about (ONLY use the data provided below):\n\n"
            for i, product in enumerate(products, 1):
                product_details += f"""
Product {i}:
- Name: {product['title']}
- Brand/Vendor: {product.get('vendor') or 'Not specified'}
- Type: {product.get('product_type') or 'Not specified'}
- Price Range: ${product['min_price']:.2f} - ${product['max_price']:.2f}
- On Sale: {'Yes' if product.get('has_discount') else 'No'}
- Tags: {', '.join(product['tags']) if product.get('tags') else 'Not available'}
---"""
        
        system_message = SystemMessage(content="""
You are a helpful e-commerce assistant answering questions about specific products.

CRITICAL RULES:
1. ONLY use information that is EXPLICITLY provided in the product data below
2. DO NOT make up, assume, or infer ANY information not present in the data
3. If information is not available, clearly state "I don't have that information" or similar
4. NEVER volunteer additional details not asked about or not present in the data

Guidelines:
- Answer ONLY what is asked, using ONLY the provided product information
- If data is missing (e.g., description is None, tags are empty), say you don't have that information
- Be precise: if asked about material and it's not in the data, say "The material information is not available"
- Don't make assumptions like "typically these products..." or "usually this type..."
- Keep a friendly, helpful tone while being strictly factual
        """)
        
        user_message = HumanMessage(content=f"""
Customer's question:
{state.chat_messages_str}

{product_details}

Please answer the customer's question about this product.
        """)
        
        messages = [system_message, user_message]
        answer = llm.invoke(messages)
        
        print(f"✅ Answer confidence: {answer.confidence}")
        
        # Create product card(s) for the product(s) being discussed
        product_ids = [p['id'] for p in products]
        product_cards = fetch_product_cards_by_ids(product_ids, state.tenant_id)
        
        # Create response with product cards and answer
        state.chat_server_response = ChatServerResponse(
            message=answer.answer,
            products=product_cards
        )
        
    except Exception as e:
        print(f"❌ Error generating answer: {e}")
        state.error = f"Answer generation failed: {str(e)}"
        state.chat_server_response = ChatServerResponse(
            message="I apologize, but I'm having trouble answering your question about that product. Please try rephrasing your question."
        )
    
    return state