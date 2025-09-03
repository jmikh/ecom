"""
Common product utilities used across agent nodes

This module provides reusable functions for fetching product data from the database.
All functions are traceable for monitoring and debugging with LangSmith.
"""

from typing import List, Dict, Any, Optional
from langsmith import traceable
from src.shared.schemas import ProductCard
from src.database import get_database


@traceable(name="fetch_product_cards_by_ids")
def fetch_product_cards_by_ids(product_ids: List[int], tenant_id: str) -> List[ProductCard]:
    """
    Fetch product details from database and return as ProductCard objects.
    
    This function is optimized for displaying products to users with minimal data.
    It fetches only the essential fields needed for ProductCard display.
    
    Args:
        product_ids: List of product IDs to fetch
        tenant_id: Tenant ID for the products (for multi-tenant isolation)
        
    Returns:
        List of ProductCard objects with product details, ordered by input ID order
        
    Note:
        - Returns empty list if product_ids is empty
        - Preserves the order of product_ids in the result
        - Includes the primary image (position=1) for each product
    """
    if not product_ids:
        return []
    
    db = get_database()
    
    # Query fetches essential product details with primary image
    # LEFT JOIN ensures products without images are still returned
    query = """
        SELECT 
            p.id,
            p.shopify_id,
            p.title, 
            p.vendor, 
            p.min_price, 
            p.max_price, 
            p.has_discount, 
            pi.src as image_url
        FROM products p
        LEFT JOIN product_images pi ON p.id = pi.product_id 
            AND pi.position = 1
        WHERE p.id = ANY(%s) 
            AND p.tenant_id = %s
        ORDER BY array_position(%s::int[], p.id)
    """
    
    # Execute query - product_ids appears twice:
    # 1. First for the WHERE IN clause
    # 2. Second for array_position ordering to maintain input order
    results = db.run_read(
        query, 
        (product_ids, tenant_id, product_ids),
        tenant_id=tenant_id
    )
    
    # Convert database rows to ProductCard objects
    # Handle potential None values and type conversions
    product_cards = []
    for row in results:
        product_cards.append(ProductCard(
            id=row['id'],
            shopify_id=str(row['shopify_id']) if row.get('shopify_id') else None,
            name=row['title'],
            vendor=row['vendor'] or '',
            image_url=row.get('image_url'),
            price_min=float(row['min_price']) if row['min_price'] else 0,
            price_max=float(row['max_price']) if row['max_price'] else 0,
            has_discount=row['has_discount'] or False
        ))
    
    return product_cards



@traceable(name="get_products_details_by_ids")
def get_products_details_by_ids(product_ids: List[int], tenant_id: str) -> List[Dict[str, Any]]:
    """
    Get essential product details for multiple product IDs.
    
    This function fetches key product information needed for product descriptions
    and recommendations. Optimized to return only essential fields for multiple products.
    
    Args:
        product_ids: List of product IDs to fetch
        tenant_id: Tenant ID for the products (for multi-tenant isolation)
        
    Returns:
        List of dictionaries with essential product details.
        
        Each dictionary includes:
        - id: Product ID
        - title: Product name
        - product_type: Category/type of product
        - body_html: Full product description
        - min_price: Minimum price across variants
        - max_price: Maximum price across variants
        - options: Product options/variations (JSONB)
        - tags: Product tags for categorization (array)
        
    Note:
        - Returns empty list if product_ids is empty
        - Preserves the order of product_ids in the result
        - Only returns products that exist and belong to the tenant
    """
    if not product_ids:
        return []
    
    db = get_database()
    
    # Streamlined query for essential product details only
    # ORDER BY array_position maintains the input order
    query = """
        SELECT 
            p.id,
            p.title,
            p.product_type,
            p.body_html,
            p.min_price,
            p.max_price,
            p.options,
            p.tags
        FROM products p
        WHERE p.id = ANY(%s) 
            AND p.tenant_id = %s
        ORDER BY array_position(%s::int[], p.id)
    """
    
    # Execute query - product_ids appears twice for WHERE and ORDER BY
    results = db.run_read(
        query,
        (product_ids, tenant_id, product_ids),
        tenant_id=tenant_id
    )
    
    # Build result list with essential fields only
    # Convert Decimal types to float for JSON serialization
    products = []
    for row in results:
        products.append({
            'id': row['id'],
            'title': row['title'],
            'product_type': row['product_type'],
            'body_html': row['body_html'],
            'min_price': float(row['min_price']) if row['min_price'] else None,
            'max_price': float(row['max_price']) if row['max_price'] else None,
            'options': row['options'],  # Already JSONB in database
            'tags': row['tags']  # Array field
        })
    
    return products


@traceable(name="get_unique_product_types")
def get_unique_product_types(tenant_id: str) -> List[str]:
    """
    Get a list of unique product types for a given tenant.
    
    This function fetches all distinct product_type values from the products table
    for a specific tenant. Useful for understanding available product categories.
    
    Args:
        tenant_id: Tenant ID to fetch product types for
        
    Returns:
        List of unique product type strings, sorted alphabetically.
        
    Example:
        >>> get_unique_product_types("tenant-123")
        ['Bag', 'Jacket', 'Shirt', 'Shoe']
        
    Note:
        - Returns empty list if no products exist for the tenant
        - Filters out NULL product types
        - Results are sorted alphabetically for consistency
    """
    db = get_database()
    
    # Query to fetch distinct product types
    # WHERE clause filters by tenant and excludes NULL product types
    query = """
        SELECT DISTINCT product_type
        FROM products
        WHERE tenant_id = %s
            AND product_type IS NOT NULL
        ORDER BY product_type ASC
    """
    
    # Execute query
    results = db.run_read(
        query,
        (tenant_id,),
        tenant_id=tenant_id
    )
    
    # Extract product types from results
    product_types = [row['product_type'] for row in results]
    
    return product_types