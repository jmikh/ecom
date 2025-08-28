"""
Simplified Database Tool for Product Search
Single unified tool that combines SQL and semantic search
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

from ..config import config
from ...database.database_pool import get_database

LIMIT=1000

# DatabaseConnection class removed - now using connection pool from database_pool.py
# The pool handles connection management, tenant isolation, and safety settings automatically


class SearchProductsInput(BaseModel):
    """
    Parameters for the search_products tool.
    The LLM fills this schema, and your tool uses it to run SQL + ANN queries.
    """
    filters: Dict[str, object] = Field(
        default_factory=dict,
        description="""Low-cardinality exact filters (product_type, min_price, max_price, vendor, has_discount, tags).
        Example: {"product_type":"Shoes","max_price":100,"vendor":"Nike","has_discount":true}"""
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


class DatabaseTools:
    """Simplified database tool with single search interface"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.embeddings = OpenAIEmbeddings(
            model=config.openai_embedding_model,
            openai_api_key=config.openai_api_key
        )
    
    def _serialize_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
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
    
    def _filters_search(self, filters: Dict[str, Any], limit: int) -> List[int]:
        """Build and execute SQL query from filters, return list of product IDs"""
        where_clauses = ["tenant_id = %s"]
        params = [self.tenant_id]
        
        # Handle different filter types
        if 'product_type' in filters:
            where_clauses.append("product_type = %s")
            params.append(filters['product_type'])
        
        if 'vendor' in filters:
            where_clauses.append("vendor = %s")
            params.append(filters['vendor'])
        
        if 'min_price' in filters:
            where_clauses.append("max_price >= %s")
            params.append(filters['min_price'])
        
        if 'max_price' in filters:
            where_clauses.append("min_price <= %s")
            params.append(filters['max_price'])
        
        if 'has_discount' in filters:
            where_clauses.append("has_discount = %s")
            params.append(filters['has_discount'])
        
        if 'tags' in filters:
            # Handle tags with ILIKE for partial matching
            where_clauses.append("tags ILIKE %s")
            params.append(f"%{filters['tags']}%")
        
        # Handle options (JSONB) - for things like size, color
        for key, value in filters.items():
            if key.startswith('option_'):
                option_name = key.replace('option_', '')
                if isinstance(value, list):
                    # Handle array of values (e.g., multiple sizes)
                    where_clauses.append("options @> %s::jsonb")
                    params.append(json.dumps({option_name: value}))
                else:
                    # Single value
                    where_clauses.append("options @> %s::jsonb")
                    params.append(json.dumps({option_name: [value]}))
        
        query = f"""
            SELECT id
            FROM products
            WHERE {' AND '.join(where_clauses)}
            ORDER BY updated_at DESC
            LIMIT %s
        """
        params.append(limit)
        
        # Execute query using connection pool
        # The pool automatically handles connection reuse, tenant context, and safety settings
        db = get_database()
        results = db.run_read(query, tuple(params), tenant_id=self.tenant_id)
        return [row['id'] for row in results]
    
    def _semantic_search(self, query: str, limit: int, filter_ids: List[int] = []) -> List[Tuple[int, float]]:
        """Execute semantic similarity search, return list of (product_id, similarity_score) tuples"""
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)
        
        # Build query with optional ID filter
        where_clauses = ["tenant_id = %s"]
        params = [query_embedding, self.tenant_id]
        
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
        results = db.run_read(query, tuple(params), tenant_id=self.tenant_id)
        
        # Filter by similarity threshold and return (id, score) tuples
        filtered_results = []
        for row in results:
            filtered_results.append((row['id'], float(row['similarity'])))
        
        return filtered_results
    
    def _get_products_by_ids(self, product_ids: List[int]) -> List[Dict[str, Any]]:
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
        results = db.run_read(query, (self.tenant_id, product_ids), tenant_id=self.tenant_id)
        
        # Create a mapping to preserve order
        products = []
        for product_id in product_ids:
            for row in results:
                if row['id'] == product_id:
                    product = self._serialize_product(dict(row))
                    products.append(product)
                    break
        
        return products
    
    def search_products(self, input_data: SearchProductsInput) -> List[Dict[str, Any]]:
        """
        Unified product search tool that combines SQL and semantic search.
        """
        filters = input_data.filters
        semantic_query = input_data.semantic_query
        k = input_data.k
        product_ids = []
        similarity_scores = {}

        # TODO(perf): combine all three queries
        
        # Step 1: Execute SQL search if filters provided
        if filters:
            product_ids = self._filters_search(filters, LIMIT)  # Get more for semantic reranking
        
        # Step 2: Execute semantic search if needed
        if semantic_query:
            semantic_results = self._semantic_search(semantic_query, LIMIT, product_ids)
            # Extract IDs and scores from tuples
            product_ids = []
            similarity_scores = {}
            for product_id, score in semantic_results:
                product_ids.append(product_id)
                similarity_scores[product_id] = score
        
        # Step 3: Convert IDs to full product dictionaries
        products = self._get_products_by_ids(product_ids[:k])
        
        # Step 4: Add similarity scores if we have them
        if similarity_scores:
            for product in products:
                if product['id'] in similarity_scores:
                    product['similarity_score'] = similarity_scores[product['id']]
        
        return products
    
    def get_traced_tool(self):
        """Get tool with native LangSmith tracing"""
        
        @tool
        def search_products(
            filters: dict = None,
            semantic_query: str = None,
            k: int = 12
        ) -> list:
            """
            Search for products using filters and/or semantic query.
            
            Args:
                filters: Dict of exact filters like product_type, min_price, max_price, vendor
                semantic_query: Natural language query for semantic search
                k: Number of results to return (default 12, max 50)
            
            Returns:
                List of product dictionaries matching the search criteria
            """
            # Create input model
            input_data = SearchProductsInput(
                filters=filters or {},
                semantic_query=semantic_query,
                k=min(k, 25),  # Cap at 25
            )
            
            return self.search_products(input_data)
        
        return search_products