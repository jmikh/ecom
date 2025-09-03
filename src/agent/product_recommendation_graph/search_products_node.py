"""
Search Products Node - Uses LLM with search tool to find products
"""

import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.config import config
from src.agent.graph_state import GraphState
from src.tools.product_search import create_product_search_tool


def search_products_node(state: GraphState) -> GraphState:
    """Node: Use LLM with search tool to find products based on user query"""
    print(f"\n{'='*60}")
    print(f"🔍 SEARCH_PRODUCTS_NODE: Executing product search")
    print(f"{'='*60}")
    
    try:
        # Create LLM for search
        llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.1,
            openai_api_key=config.openai_api_key
        )
        
        # Create product search tool bound to tenant
        search_tool = create_product_search_tool(state.tenant_id)
        
        # Bind tool to LLM for search
        llm_with_tools = llm.bind_tools([search_tool])
        
        system_message = SystemMessage(content="""
You are a product search assistant. Use the search_products tool to find products based on the user's request.
The tool description contains detailed instructions on how to use it effectively.
Always search for 15-20 products to give good options for relevance filtering later.
        """)
        
        user_message = HumanMessage(content=f"""
User request: {state.chat_messages_str}

Search for products that might match this request. Cast a wide net to get good coverage.
        """)
        
        # Execute search
        print("📊 Calling search tool...")
        response = llm_with_tools.invoke([system_message, user_message])
        
        # Parse tool calls and get results
        found_products = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call['name'] == 'search_products':
                    print(f"   Search arguments: {tool_call['args']}")
                    # Execute the tool with the arguments
                    products_json = search_tool.invoke(tool_call['args'])
                    found_products = json.loads(products_json) if isinstance(products_json, str) else products_json
                    break
        
        print(f"📦 Found {len(found_products)} products from search")
        
        # Initialize workflow_params if needed
        if not state.workflow_params:
            state.workflow_params = {}
        
        # Store search results in workflow_params
        state.workflow_params["search_products"] = found_products
        
    except Exception as e:
        print(f"❌ Error in search_products_node: {e}")
        state.error = f"Product search failed: {str(e)}"
        
        # Initialize workflow_params if needed and store empty results
        if not state.workflow_params:
            state.workflow_params = {}
        state.workflow_params["search_products"] = []
        
    return state