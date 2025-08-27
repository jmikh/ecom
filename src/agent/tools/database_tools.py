"""
Database Tools for LangGraph Agent
Safe SQL execution and vector similarity search
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain.tools import Tool
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

from ..config import config


class DatabaseConnection:
    """Manages database connections with safety measures"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.conn = None
        self.cursor = None
    
    def __enter__(self):
        self.conn = psycopg2.connect(
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        # Set tenant context for RLS
        self.cursor.execute("SET app.tenant_id = %s", (self.tenant_id,))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()


class SQLSearchInput(BaseModel):
    """Input for SQL search tool"""
    filters: Dict[str, Any] = Field(
        description="Dictionary of filters: product_type, min_price, max_price, has_discount, vendor, etc."
    )
    limit: int = Field(default=20, description="Number of results to return")


class SemanticSearchInput(BaseModel):
    """Input for semantic search tool"""
    query: str = Field(description="Natural language search query")
    limit: int = Field(default=20, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Optional SQL filters to apply before semantic search"
    )


class ProductInfoInput(BaseModel):
    """Input for getting product details"""
    product_ids: List[int] = Field(description="List of product IDs to get details for")


class DatabaseTools:
    """Safe database interaction tools for the agent"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.embeddings = OpenAIEmbeddings(
            model=config.openai_embedding_model,
            openai_api_key=config.openai_api_key
        )
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information for the tenant"""
        with DatabaseConnection(self.tenant_id) as db:
            # Get unique product types
            db.cursor.execute("""
                SELECT DISTINCT product_type 
                FROM products 
                WHERE tenant_id = %s AND product_type IS NOT NULL
                ORDER BY product_type
            """, (self.tenant_id,))
            product_types = [row['product_type'] for row in db.cursor.fetchall()]
            
            # Get unique vendors
            db.cursor.execute("""
                SELECT DISTINCT vendor 
                FROM products 
                WHERE tenant_id = %s AND vendor IS NOT NULL
                ORDER BY vendor
            """, (self.tenant_id,))
            vendors = [row['vendor'] for row in db.cursor.fetchall()]
            
            # Get price range
            db.cursor.execute("""
                SELECT MIN(min_price) as min_price, MAX(max_price) as max_price
                FROM products 
                WHERE tenant_id = %s
            """, (self.tenant_id,))
            price_range = db.cursor.fetchone()
            
            # Get available options
            db.cursor.execute("""
                SELECT DISTINCT jsonb_object_keys(options) as option_key
                FROM products 
                WHERE tenant_id = %s AND options IS NOT NULL
            """, (self.tenant_id,))
            option_keys = [row['option_key'] for row in db.cursor.fetchall()]
            
            return {
                "product_types": product_types,
                "vendors": vendors,
                "price_range": {
                    "min": float(price_range['min_price']) if price_range['min_price'] else 0,
                    "max": float(price_range['max_price']) if price_range['max_price'] else 0
                },
                "available_options": option_keys,
                "total_products": self._count_products()
            }
    
    def _count_products(self) -> int:
        """Count total products for tenant"""
        with DatabaseConnection(self.tenant_id) as db:
            db.cursor.execute(
                "SELECT COUNT(*) as count FROM products WHERE tenant_id = %s",
                (self.tenant_id,)
            )
            return db.cursor.fetchone()['count']
    
    def sql_search(self, filters: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """
        Execute safe SQL search with filters
        Returns products matching the SQL criteria
        """
        with DatabaseConnection(self.tenant_id) as db:
            # Build WHERE clause safely
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
                where_clauses.append("min_price >= %s")
                params.append(filters['min_price'])
            
            if 'max_price' in filters:
                where_clauses.append("max_price <= %s")
                params.append(filters['max_price'])
            
            if 'has_discount' in filters:
                where_clauses.append("has_discount = %s")
                params.append(filters['has_discount'])
            
            if 'tags' in filters:
                # Handle tags with ILIKE for partial matching
                where_clauses.append("tags ILIKE %s")
                params.append(f"%{filters['tags']}%")
            
            # Handle options (JSONB)
            for key, value in filters.items():
                if key.startswith('option_'):
                    option_name = key.replace('option_', '')
                    where_clauses.append("options @> %s::jsonb")
                    params.append(json.dumps({option_name: [value]}))
            
            # Build and execute query
            query = f"""
                SELECT 
                    id, shopify_id, title, vendor, product_type,
                    min_price, max_price, has_discount, 
                    options, tags, handle
                FROM products
                WHERE {' AND '.join(where_clauses)}
                ORDER BY updated_at DESC
                LIMIT %s
            """
            params.append(min(limit, config.max_sql_results))
            
            db.cursor.execute(query, params)
            results = db.cursor.fetchall()
            
            # Convert to regular dicts and handle decimal/json types
            return [self._serialize_product(dict(row)) for row in results]
    
    def semantic_search(self, query: str, limit: int = 20, 
                       filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute semantic similarity search using embeddings
        Optionally apply SQL filters first
        """
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)
        
        with DatabaseConnection(self.tenant_id) as db:
            # Build base query with optional filters
            where_clauses = ["p.tenant_id = %s"]
            where_params = [self.tenant_id]
            
            if filters:
                # Add SQL filters (reuse logic from sql_search)
                for key, value in filters.items():
                    if key == 'product_type':
                        where_clauses.append("p.product_type = %s")
                        where_params.append(value)
                    elif key == 'min_price':
                        where_clauses.append("p.min_price >= %s")
                        where_params.append(value)
                    elif key == 'max_price':
                        where_clauses.append("p.max_price <= %s")
                        where_params.append(value)
                    elif key == 'has_discount':
                        where_clauses.append("p.has_discount = %s")
                        where_params.append(value)
            
            # Semantic search query with cosine similarity
            # Parameters order: [embedding_vector, where_params..., limit]
            query = f"""
                SELECT 
                    p.id, p.shopify_id, p.title, p.vendor, p.product_type,
                    p.min_price, p.max_price, p.has_discount, 
                    p.options, p.tags, p.handle,
                    1 - (pe.embedding <=> %s::vector) as similarity
                FROM products p
                JOIN product_embeddings pe ON p.id = pe.product_id AND p.tenant_id = pe.tenant_id
                WHERE {' AND '.join(where_clauses)}
                    AND pe.embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s
            """
            
            # Build parameter list in correct order: embedding first, then WHERE params, then limit
            params = [query_embedding] + where_params + [min(limit, config.max_sql_results)]
            
            
            db.cursor.execute(query, params)
            results = db.cursor.fetchall()
            
            # Filter by similarity threshold and serialize
            filtered_results = []
            for row in results:
                if row['similarity'] >= config.similarity_threshold:
                    product = self._serialize_product(dict(row))
                    product['similarity_score'] = float(row['similarity'])
                    filtered_results.append(product)
            
            return filtered_results
    
    def get_product_details(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get detailed information for specific products
        Includes variants and images
        """
        if not product_ids:
            return []
        
        with DatabaseConnection(self.tenant_id) as db:
            # Get products with full details
            db.cursor.execute("""
                SELECT 
                    p.*,
                    array_agg(DISTINCT jsonb_build_object(
                        'id', v.id,
                        'title', v.title,
                        'price', v.price,
                        'sku', v.sku,
                        'option1', v.option1,
                        'option2', v.option2,
                        'option3', v.option3
                    )) FILTER (WHERE v.id IS NOT NULL) as variants,
                    array_agg(DISTINCT jsonb_build_object(
                        'id', i.id,
                        'src', i.src,
                        'alt', i.alt,
                        'position', i.position
                    )) FILTER (WHERE i.id IS NOT NULL) as images
                FROM products p
                LEFT JOIN product_variants v ON p.id = v.product_id
                LEFT JOIN product_images i ON p.id = i.product_id
                WHERE p.tenant_id = %s AND p.id = ANY(%s)
                GROUP BY p.id
            """, (self.tenant_id, product_ids))
            
            results = db.cursor.fetchall()
            return [self._serialize_product(dict(row), include_details=True) for row in results]
    
    def get_similar_products(self, product_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find similar products based on embedding similarity
        """
        with DatabaseConnection(self.tenant_id) as db:
            # Get the product's embedding
            db.cursor.execute("""
                SELECT embedding 
                FROM product_embeddings 
                WHERE tenant_id = %s AND product_id = %s
            """, (self.tenant_id, product_id))
            
            result = db.cursor.fetchone()
            if not result or not result['embedding']:
                return []
            
            # Find similar products
            db.cursor.execute("""
                SELECT 
                    p.id, p.shopify_id, p.title, p.vendor, p.product_type,
                    p.min_price, p.max_price, p.has_discount, 
                    p.options, p.tags, p.handle,
                    1 - (pe.embedding <=> %s::vector) as similarity
                FROM products p
                JOIN product_embeddings pe ON p.id = pe.product_id AND p.tenant_id = pe.tenant_id
                WHERE p.tenant_id = %s 
                    AND p.id != %s
                    AND pe.embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s
            """, (result['embedding'], self.tenant_id, product_id, limit))
            
            results = db.cursor.fetchall()
            similar_products = []
            for row in results:
                product = self._serialize_product(dict(row))
                product['similarity_score'] = float(row['similarity'])
                similar_products.append(product)
            
            return similar_products
    
    def _serialize_product(self, product: Dict[str, Any], include_details: bool = False) -> Dict[str, Any]:
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
        
        # Handle body_html for details view
        if include_details and 'body_html' in product:
            # Keep full HTML in details
            pass
        elif 'body_html' in product:
            # Remove from summary view
            del product['body_html']
        
        return product
    
    # Native LangSmith-traced tools using @tool decorator
    def get_traced_tools(self):
        """Get tools with native LangSmith tracing"""
        
        @tool
        def sql_search_tool(filters: dict, limit: int = 20) -> list:
            """Search products using SQL filters like product_type, price range, vendor, discount status"""
            return self.sql_search(filters, limit)
        
        @tool 
        def semantic_search_tool(query: str, limit: int = 20) -> list:
            """Search products using natural language semantic similarity"""
            return self.semantic_search(query, limit)
        
        @tool
        def get_schema_info_tool() -> dict:
            """Get database schema information including product types, vendors, price ranges, and available options"""
            return self.get_schema_info()
        
        @tool
        def get_product_details_tool(product_ids: list) -> list:
            """Get detailed information about specific products including variants and images"""
            return self.get_product_details(product_ids)
        
        @tool
        def get_similar_products_tool(product_id: str, limit: int = 5) -> list:
            """Find similar products based on vector similarity"""
            return self.get_similar_products(product_id, limit)
        
        return [
            sql_search_tool,
            semantic_search_tool,
            get_schema_info_tool,
            get_product_details_tool,
            get_similar_products_tool
        ]
    
    def create_tools(self) -> List[Tool]:
        """Create LangChain tools for the agent"""
        return [
            Tool(
                name="get_schema_info",
                description="Get database schema information including product types, vendors, price ranges, and available options",
                func=self.get_schema_info
            ),
            Tool(
                name="sql_search", 
                description="Search products using SQL filters like product_type, price range, vendor, discount status",
                func=lambda filters_str: self.sql_search(json.loads(filters_str) if isinstance(filters_str, str) else filters_str)
            ),
            Tool(
                name="semantic_search",
                description="Search products using natural language semantic similarity",
                func=lambda query: self.semantic_search(query)
            ),
            Tool(
                name="get_product_details",
                description="Get detailed information about specific products including variants and images",
                func=lambda ids_str: self.get_product_details(json.loads(ids_str) if isinstance(ids_str, str) else ids_str)
            ),
            Tool(
                name="get_similar_products",
                description="Find products similar to a given product based on embeddings",
                func=lambda product_id: self.get_similar_products(int(product_id))
            )
        ]