"""
Fetch Candidate Products Node - Database search functionality for products
Extracts the database search logic and converts it to a LangGraph node
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from langchain_openai import OpenAIEmbeddings

from src.agent.config import config
from src.database import get_database
from src.agent.graph_state import GraphState
from src.agent.get_product_filters_node import ProductsFilter, SqlFilter
from langsmith import traceable

LIMIT = 1000


def _serialize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize product data for JSON response"""
    # Handle decimal types
    for field in ['min_price', 'max_price']:
        if product.get(field) is not None:
            product[field] = float(product[field])
    
    # Clean up None values
    product = {k: v for k, v in product.items() if v is not None}
    
    # Format timestamps
    for field in ['created_at', 'updated_at', 'published_at']:
        if field in product and isinstance(product[field], datetime):
            product[field] = product[field].isoformat()
    
    # Remove internal fields
    fields_to_remove = ['tenant_id', 'body_html']
    for field in fields_to_remove:
        product.pop(field, None)
    
    return product


@traceable(name="sql_product_filter_search")
def _filters_search(tenant_id: str, filters: SqlFilter, limit: int) -> List[int]:
    """Build and execute SQL query from filters, return list of product IDs"""
    where_clauses = ["tenant_id = %s"]
    params = [tenant_id]
    
    # Handle SqlFilter fields only
    if filters.product_type:
        where_clauses.append("product_type = %s")
        params.append(filters.product_type)
    
    if filters.min_price is not None:
        where_clauses.append("max_price >= %s")
        params.append(filters.min_price)
    
    if filters.max_price is not None:
        where_clauses.append("min_price <= %s")
        params.append(filters.max_price)
    
    if filters.has_discount is not None:
        where_clauses.append("has_discount = %s")
        params.append(filters.has_discount)
    
    query = f"""
        SELECT id
        FROM products
        WHERE {' AND '.join(where_clauses)}
        ORDER BY updated_at DESC
        LIMIT %s
    """
    params.append(limit)
    
    # Execute query using connection pool
    db = get_database()
    results = db.run_read(query, tuple(params), tenant_id=tenant_id)
    return [row['id'] for row in results]


@traceable(name="sql_product_semantic_search")
def _semantic_search(tenant_id: str, embeddings: OpenAIEmbeddings, query: str, limit: int, filter_ids: List[int] = []) -> List[Tuple[int, float]]:
    """Execute semantic similarity search, return list of (product_id, similarity_score) tuples"""
    # Generate query embedding
    query_embedding = embeddings.embed_query(query)
    
    # Build query with optional ID filter
    where_clauses = ["tenant_id = %s"]
    params = [query_embedding, tenant_id]
    
    if filter_ids:
        # Limit to specific product IDs from SQL results
        where_clauses.append("id = ANY(%s)")
        params.append(filter_ids)
    
    query = f"""
        SELECT 
            id,
            1 - (embedding <=> %s::vector) as similarity
        FROM products
        WHERE {' AND '.join(where_clauses)}
            AND embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT %s
    """
    params.append(limit)
    
    # Execute query using connection pool
    db = get_database()
    results = db.run_read(query, tuple(params), tenant_id=tenant_id)
    
    # Filter by similarity threshold and return (id, score) tuples
    filtered_results = []
    for row in results:
        filtered_results.append((row['id'], float(row['similarity'])))
    
    return filtered_results


@traceable(name="sql_product_description_fetch")
def _get_products_by_ids(tenant_id: str, product_ids: List[int]) -> List[Dict[str, Any]]:
    """Convert product IDs to full product dictionaries"""
    if not product_ids:
        return []
    
    query = """
        SELECT 
            id, shopify_id, title, vendor, product_type,
            min_price, max_price, has_discount, 
            options, tags, handle, status,
            created_at, updated_at, published_at
        FROM products
        WHERE tenant_id = %s AND id = ANY(%s)
    """
    
    # Execute query using connection pool
    db = get_database()
    results = db.run_read(query, (tenant_id, product_ids), tenant_id=tenant_id)
    
    # Create a mapping to preserve order
    products = []
    for product_id in product_ids:
        for row in results:
            if row['id'] == product_id:
                product = _serialize_product(dict(row))
                products.append(product)
                break
    
    return products


def search_products(tenant_id: str, filter: ProductsFilter) -> List[Dict[str, Any]]:
    """
    Unified product search that combines SQL and semantic search.
    """
    product_ids = []
    similarity_scores = {}
    
    # Initialize embeddings if needed for semantic search
    embeddings = None
    if filter.semantic_query:
        embeddings = OpenAIEmbeddings(
            model=config.openai_embedding_model,
            openai_api_key=config.openai_api_key
        )

    # TODO(perf): combine all three queries
    
    # Step 1: Execute SQL search if filters provided
    if filter.sql_filters:
        product_ids = _filters_search(tenant_id, filter.sql_filters, LIMIT)  # Get more for semantic reranking
    
    # Step 2: Execute semantic search if needed
    if filter.semantic_query and embeddings:
        semantic_results = _semantic_search(tenant_id, embeddings, filter.semantic_query, LIMIT, product_ids)
        # Extract IDs and scores from tuples
        product_ids = []
        similarity_scores = {}
        for product_id, score in semantic_results:
            product_ids.append(product_id)
            similarity_scores[product_id] = score
    
    # Step 3: Convert IDs to full product dictionaries
    products = _get_products_by_ids(tenant_id, product_ids[:filter.k])
    
    # Step 4: Add similarity scores if we have them
    if similarity_scores:
        for product in products:
            if product['id'] in similarity_scores:
                product['similarity_score'] = similarity_scores[product['id']]
    
    return products


def fetch_candidate_products_node(state: GraphState) -> GraphState:
    """Node: Fetch candidate products based on extracted filters"""
    print(f"\n{'='*60}")
    print(f"🔍 FETCH_CANDIDATE_PRODUCTS_NODE: Starting product search")
    print(f"{'='*60}")
    
    try:
        if not state.products_filter:
            raise ValueError("No product filters found in state")
        
        # Perform product search
        products = search_products(state.tenant_id, state.products_filter)
        
        # Store results in state
        state.finalist_products = products
        
        print(f"✅ Found {len(products)} candidate products")
        
    except Exception as e:
        print(f"❌ Error fetching products: {e}")
        state.error = f"Product search failed: {str(e)}"
        
    return state