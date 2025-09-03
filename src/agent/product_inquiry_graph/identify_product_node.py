"""
Product Identification Node
Identifies which product(s) the user is asking about from conversation
Uses product search tool to find actual products in the catalog
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json

from src.agent.graph_state import GraphState
from src.agent.config import config
from src.shared.schemas import ChatServerResponse
from src.agent.common import fetch_product_cards_by_ids
from src.tools import create_product_search_tool


class ProductIdentificationResult(BaseModel):
    """Result of product identification from user query"""
    
    # Either we found specific products...
    identified_product_ids: Optional[List[int]] = Field(
        None,
        description="List of product IDs that match what the user is asking about"
    )
    
    # ...or we need clarification
    needs_clarification: bool = Field(
        default=False,
        description="True if we need to ask the user for clarification"
    )
    
    clarification_message: Optional[str] = Field(
        None,
        description="Message to ask user for clarification (required if needs_clarification=True)"
    )
    
    # Optional: Show product options when clarifying
    clarification_product_ids: Optional[List[int]] = Field(
        None,
        description="Product IDs to show as options when asking for clarification (e.g., 'Which of these products did you mean?')"
    )


def identify_product_node(state: GraphState) -> GraphState:
    """
    Identify which product(s) the user is asking about.
    
    Strategy:
    1. First try to extract product IDs from conversation history
    2. If ambiguous, prepare clarification with product options
    3. If products not shown yet, search and present options
    """
    print(f"\n{'='*60}")
    print(f"🔍 IDENTIFY_PRODUCT_NODE: Identifying products from user query")
    print(f"{'='*60}")
    
    try:
        # Get tenant ID from state
        tenant_id = state.tenant_id
        
        # Create LLM for structured output
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.1,
            openai_api_key=config.openai_api_key
        )
        
        # First, try to identify products from conversation history
        llm_structured = llm.with_structured_output(ProductIdentificationResult)
        
        initial_system_message = SystemMessage(content="""
You are identifying which products a user is asking about based on ACTUAL conversation history.

CRITICAL RULES:
1. ONLY extract product IDs that appear in the ACTUAL conversation history provided
2. NEVER use example IDs (like 123, 456, etc.) - these are just illustrations
3. If NO products have been mentioned in the conversation, you MUST set needs_clarification = true

STEP 1: Extract product IDs from conversation
- Look for product IDs in the ACTUAL conversation messages (format: [ID: XXX], "id": XXX, or product ID XXX)
- When user says "that product", "the jacket", "those shirts" - find the ACTUAL IDs shown earlier
- If multiple products of same type were shown, note ALL their ACTUAL IDs

STEP 2: Determine if you can identify the products
- If you found clear product ID(s) IN THE CONVERSATION → set identified_product_ids
- If reference is ambiguous (e.g., "the bag" but 2 bags shown) → needs_clarification = true
- If products haven't been shown AT ALL → needs_clarification = true, leave clarification_product_ids empty

STEP 3: For ambiguous cases
- Set clarification_message asking which product they mean (WITHOUT mentioning IDs to the user)
- Include the ACTUAL product IDs from conversation in clarification_product_ids (for internal use only)

IMPORTANT for clarification_message:
- NEVER mention "product ID" or numbers to the user
- Say things like: "Which shirt are you referring to?", "Could you specify which jacket?", "Which of these products did you mean?"
- Keep messages natural and user-friendly

IMPORTANT: The following are ONLY examples of the format - DO NOT use these actual ID numbers:
- User asks about "product 456" that WAS mentioned → identified_product_ids: [456]
- User asks about "those shirts" when shirts WERE shown → identified_product_ids: [actual_ids_from_conversation]
- User asks about "leather bags" when NONE shown → needs_clarification: true, clarification_product_ids: []
        """)
        
        initial_user_message = HumanMessage(content=f"""
Conversation history:
{state.chat_messages_str}

Identify which product(s) the user is asking about.
Extract product IDs if they're mentioned in the conversation.
        """)
        
        # Get initial identification
        identification = llm_structured.invoke([initial_system_message, initial_user_message])
        
        print(f"📊 Initial identification:")
        print(f"   - Identified IDs: {identification.identified_product_ids}")
        print(f"   - Needs clarification: {identification.needs_clarification}")
        
        # If we need clarification and no products to show, search for them
        if identification.needs_clarification and not identification.clarification_product_ids:
            print(f"🔍 Need to search for products to show as options...")
            
            # Create search tool
            product_search_tool = create_product_search_tool(tenant_id)
            
            # Use LLM with tools to search
            llm_with_tools = llm.bind_tools([product_search_tool])
            
            search_system_message = SystemMessage(content="""
The user is asking about products that have NOT been shown in the conversation yet.
You MUST use the search_products tool to find relevant products to show as options.

IMPORTANT: This is only called when NO matching products were found in the conversation history.
Focus on finding products that match what the user is asking about.
Limit results to 5 products maximum.
        """)
            
            search_user_message = HumanMessage(content=f"""
User's latest query: {state.chat_messages_str.split('Human:')[-1] if 'Human:' in state.chat_messages_str else state.chat_messages_str}

Search for relevant products to show as options.
        """)
            
            # Execute search
            tool_response = llm_with_tools.invoke([search_system_message, search_user_message])
            
            # Extract products from search
            search_results = []
            if hasattr(tool_response, 'tool_calls') and tool_response.tool_calls:
                for tool_call in tool_response.tool_calls:
                    if tool_call['name'] == 'search_products':
                        # Use invoke method for proper tool execution
                        result_json = product_search_tool.invoke(tool_call['args'])
                        products = json.loads(result_json) if isinstance(result_json, str) else result_json
                        if isinstance(products, list):
                            search_results = products[:5]  # Limit to 5
                            print(f"🔧 Found {len(search_results)} products to show")
            
            # Update identification with found products
            if search_results:
                identification.clarification_product_ids = [p['id'] for p in search_results]
                if not identification.clarification_message:
                    identification.clarification_message = "I found several products that might match what you're looking for. Which one are you interested in?"
        
        # Store identification result in state
        state.workflow_params = state.workflow_params or {}
        state.workflow_params['product_identification'] = identification.model_dump()
        
        # Process the result
        if identification.identified_product_ids:
            # We successfully identified specific products
            print(f"✅ Identified product IDs: {identification.identified_product_ids}")
            state.workflow_params['identified_product_ids'] = identification.identified_product_ids
            state.workflow_params['needs_clarification'] = False
            
        elif identification.needs_clarification:
            # Need to ask for clarification
            print(f"❓ Need clarification")
            
            # If we have products to show, fetch their details for display
            product_cards = []
            if identification.clarification_product_ids:
                # Use common function to fetch product cards
                product_cards = fetch_product_cards_by_ids(
                    identification.clarification_product_ids, 
                    tenant_id
                )
                print(f"📦 Prepared {len(product_cards)} product cards for clarification")
            
            # Create response with clarification
            state.chat_server_response = ChatServerResponse(
                message=identification.clarification_message or 
                "Could you please specify which product you're asking about?",
                products=product_cards if product_cards else None
            )
            state.workflow_params['needs_clarification'] = True
            
        else:
            # Shouldn't happen, but handle gracefully
            print(f"⚠️ No products identified and no clarification needed - unexpected state")
            state.chat_server_response = ChatServerResponse(
                message="I couldn't identify which product you're asking about. Could you please be more specific?"
            )
            state.workflow_params['needs_clarification'] = True
        
    except Exception as e:
        print(f"❌ Error identifying product: {e}")
        state.error = f"Product identification failed: {str(e)}"
        state.chat_server_response = ChatServerResponse(
            message="I'm having trouble understanding which product you're asking about. Could you please be more specific?"
        )
    
    return state