"""
Fetch Product Details Node
Looks up product information from the database based on identified product IDs
"""

from src.agent.graph_state import GraphState
from src.shared.schemas import ChatServerResponse
from src.agent.common import get_products_details_by_ids


def fetch_product_details_node(state: GraphState) -> GraphState:
    """
    Fetch full details for identified product(s) from database using their IDs
    """
    print(f"\n{'='*60}")
    print(f"📚 FETCH_PRODUCT_DETAILS_NODE: Fetching product details by ID")
    print(f"{'='*60}")
    
    try:
        # Get product IDs from previous node
        product_ids = state.workflow_params.get('identified_product_ids', [])
        if not product_ids:
            raise ValueError("No product IDs identified to fetch")
        
        print(f"📋 Fetching details for product IDs: {product_ids}")
        
        # Use common function to get complete product details
        found_products = get_products_details_by_ids(product_ids, state.tenant_id)
        
        print(f"📦 Found {len(found_products)} product(s) in database")
        
        if len(found_products) == 0:
            # Product IDs not found in database (shouldn't happen)
            state.chat_server_response = ChatServerResponse(
                message=f"I couldn't find the product details in our catalog. The product may have been removed or the ID is incorrect."
            )
            state.workflow_params['products_found'] = []
            state.workflow_params['needs_clarification'] = True
            
        else:
            # Store all found products
            state.workflow_params['products_found'] = found_products
            
            # For single product, store as selected
            if len(found_products) == 1:
                state.workflow_params['selected_product'] = found_products[0]
            else:
                # Multiple products - store them all (e.g., "are any of these waterproof?")
                state.workflow_params['selected_products'] = found_products
            
            state.workflow_params['needs_clarification'] = False
        
    except Exception as e:
        print(f"❌ Error fetching product details: {e}")
        state.error = f"Product lookup failed: {str(e)}"
        state.chat_server_response = ChatServerResponse(
            message="I encountered an error looking up that product. Please try again."
        )
    
    return state