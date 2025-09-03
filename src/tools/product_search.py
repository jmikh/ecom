"""
Product Search Tool - Database search functionality for products
Provides both direct search function and LangChain tool interface
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from langchain_openai import OpenAIEmbeddings
from langchain.tools import StructuredTool

from src.agent.config import config
from src.database import get_database
from src.agent.common import get_products_details_by_ids, get_unique_product_types
from langsmith import traceable


# Copy the filter classes here to avoid circular imports
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
        description="Number of results to return (default 5, max 25)"
    )

LIMIT = 1000


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
    # Generate query embedding with tracing
    @traceable(name="generate_query_embedding")
    def get_embedding(text: str):
        return embeddings.embed_query(text)
    
    query_embedding = get_embedding(query)
    
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
        print(f"📊 SQL filter search returned {len(product_ids)} products")
        if product_ids:
            print(f"   First few IDs: {product_ids[:5]}")
    
    # Step 2: Execute semantic search if needed
    if filter.semantic_query and embeddings:
        semantic_results = _semantic_search(tenant_id, embeddings, filter.semantic_query, LIMIT, product_ids)
        print(f"🔍 Semantic search returned {len(semantic_results)} products")
        # Extract IDs and scores from tuples
        product_ids = []
        similarity_scores = {}
        for product_id, score in semantic_results:
            product_ids.append(product_id)
            similarity_scores[product_id] = score
        if semantic_results:
            print(f"   Top scores: {[f'ID {pid}: {score:.3f}' for pid, score in semantic_results[:3]]}")
    
    # Step 3: Convert IDs to full product dictionaries using common function
    products = get_products_details_by_ids(product_ids[:filter.k], tenant_id)
    print(f"📦 Returning {len(products)} products (limited to k={filter.k})")
    
    # Step 4: Add similarity scores if we have them
    if similarity_scores:
        for product in products:
            if product['id'] in similarity_scores:
                product['similarity_score'] = similarity_scores[product['id']]
    
    return products


def create_product_search_tool(tenant_id: str) -> StructuredTool:
    """
    Create a LangChain tool for product search bound to a specific tenant
    
    Args:
        tenant_id: The tenant ID to search products for
        
    Returns:
        LangChain Tool that can be used by an agent
    """
    # Fetch available product types for this tenant
    available_product_types = get_unique_product_types(tenant_id)
    
    # Format product types for the description
    if available_product_types:
        product_types_str = ", ".join(f'"{pt}"' for pt in available_product_types)
        product_type_description = f"Category from available types: {product_types_str}"
        # Create examples using actual product types
        example_types = available_product_types[:4] if len(available_product_types) >= 4 else available_product_types
    else:
        product_type_description = "Product category (if available)"
        example_types = ["Shoe", "Shirt", "Bag", "Jacket"]  # Fallback examples
    
    # Create a partial function with tenant_id bound
    @traceable(name="product_search_tool")
    def search_with_tenant(sql_filters: SqlFilter, 
                          semantic_query: Optional[str] = None,
                          k: int = 5) -> str:
        # Create the filter object with the provided SqlFilter
        filter_obj = ProductsFilter(
            sql_filters=sql_filters,
            semantic_query=semantic_query,
            k=k
        )
        
        products = search_products(tenant_id, filter_obj)
        return json.dumps(products)
    
    # Build dynamic examples based on available product types
    examples = []
    if len(example_types) > 0:
        examples.append(f'"running shoes under $100" → sql_filters={{product_type:"{example_types[0] if "Shoe" in example_types else example_types[0]}", max_price:100}}, semantic_query:"running shoes", k:15')
    if len(example_types) > 1:
        examples.append(f'"waterproof outdoor jackets" → sql_filters={{product_type:"{example_types[1] if "Jacket" in example_types else example_types[1]}"}}, semantic_query:"waterproof outdoor", k:15')
    if len(example_types) > 2:
        examples.append(f'"shirts on sale" → sql_filters={{product_type:"{example_types[2] if "Shirt" in example_types else example_types[2]}", has_discount:true}}, k:15')
    if len(example_types) > 3:
        examples.append(f'"comfortable walking shoes" → sql_filters={{product_type:"{example_types[3] if "Shoe" in example_types else example_types[0]}"}}, semantic_query:"comfortable walking", k:10')
    
    examples_str = "\n".join(f"- {ex}" for ex in examples) if examples else "- No specific examples available"
    
    return StructuredTool(
        name="search_products",
        description=f"""Search for products in the catalog using SQL filters and/or semantic search.

AVAILABLE PRODUCT TYPES FOR THIS CATALOG:
{product_types_str if available_product_types else "No product types available"}

How to use this tool:
1. Extract filters from user query:
   - sql_filters.product_type: {product_type_description}
   - sql_filters.min_price: Minimum price if mentioned (e.g., "at least $50" → min_price=50)
   - sql_filters.max_price: Maximum price if mentioned (e.g., "under $100" → max_price=100)
   - sql_filters.has_discount: True if user wants sale/discounted items
   - semantic_query: The user's descriptive search terms for semantic matching

2. Set k (number of results):
   - For recommendations: Use 10-20 results
   - For specific searches: Use 5-10 results
   - Maximum is 25

3. Best practices:
   - Use BOTH sql_filters AND semantic_query when possible for best results
   - Always include semantic_query with the user's descriptive terms
   - Only use product types from the available list above

Examples:
{examples_str}

Returns: JSON array of product objects with id, title, vendor, price, etc.""",
        func=search_with_tenant,
        args_schema=ProductsFilter
    )