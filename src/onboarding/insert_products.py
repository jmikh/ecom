#!/usr/bin/env python3
"""
Insert Shopify products from JSON file into PostgreSQL database
"""

import json
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import execute_batch, Json
from dotenv import load_dotenv
import uuid

load_dotenv()


class ProductInserter:
    def __init__(self, tenant_id: str):
        """Initialize database connection and tenant ID"""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'ecom_products')
        }
        
        self.tenant_id = tenant_id
        print(f"Using tenant_id: {self.tenant_id}")
        
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(**self.conn_params)
        self.cursor = self.conn.cursor()
        
        # Verify tenant exists
        self.verify_tenant_exists()
        
        # Set the tenant context for RLS
        self.cursor.execute("SET app.tenant_id = %s", (self.tenant_id,))
    
    def verify_tenant_exists(self):
        """Verify that the tenant exists in the tenants table"""
        check_query = "SELECT name FROM tenants WHERE tenant_id = %s"
        self.cursor.execute(check_query, (self.tenant_id,))
        result = self.cursor.fetchone()
        
        if not result:
            print(f"ERROR: Tenant {self.tenant_id} does not exist")
            print("Please create the tenant first using: python src/database/manage_tenants.py create <name>")
            raise ValueError(f"Tenant {self.tenant_id} not found")
        else:
            print(f"Using tenant: {result[0]} ({self.tenant_id})")
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def clean_html(self, html_text: Optional[str]) -> str:
        """Extract clean text from HTML content"""
        if not html_text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_text)
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def create_embedding_json(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Create a JSON object containing the fields to embed for a product"""
        # Extract options data
        options_data = {}
        raw_options = product.get('options', [])
        for option in raw_options:
            option_name = option.get('name', '')
            option_values = option.get('values', [])
            if option_name:
                options_data[option_name] = option_values
        
        # Clean the body_html
        cleaned_body = self.clean_html(product.get('body_html'))
        
        # Create embedding content
        embedding_content = {
            "title": product.get('title', ''),
            "product_type": product.get('product_type', ''),
            "tags": product.get('tags', ''),
            "vendor": product.get('vendor', ''),
            "options": options_data,
            "description": cleaned_body
        }
        
        return embedding_content
    
    def parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse Shopify timestamp string to datetime"""
        if not timestamp_str:
            return None
        try:
            from dateutil import parser
            return parser.parse(timestamp_str)
        except:
            return None
    
    def compute_product_fields(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Compute min_price, max_price, has_discount, and options fields from variants"""
        variants = product.get('variants', [])
        
        # Calculate min and max prices
        prices = []
        has_discount = False
        
        for variant in variants:
            if variant.get('price'):
                try:
                    price = float(variant['price'])
                    prices.append(price)
                    
                    # Check for discount
                    if variant.get('compare_at_price'):
                        compare_price = float(variant['compare_at_price'])
                        if compare_price > price:
                            has_discount = True
                except (ValueError, TypeError):
                    pass
        
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        
        # Process options into a JSON structure
        options_dict = {}
        raw_options = product.get('options', [])
        
        for option in raw_options:
            option_name = option.get('name', '')
            option_values = option.get('values', [])
            if option_name:
                options_dict[option_name] = option_values
        
        return {
            'min_price': min_price,
            'max_price': max_price,
            'has_discount': has_discount,
            'options': json.dumps(options_dict) if options_dict else '{}'
        }
    
    def insert_product(self, product: Dict[str, Any]) -> Optional[int]:
        """Insert a single product into the products table"""
        computed_fields = self.compute_product_fields(product)
        embedding_json = self.create_embedding_json(product)
        
        # Delete existing product if it exists (CASCADE will delete variants and images)
        delete_query = "DELETE FROM products WHERE tenant_id = %s AND shopify_id = %s"
        self.cursor.execute(delete_query, (self.tenant_id, product.get('id')))
        
        # Insert fresh (including embedding_json, but not embedding vector yet)
        insert_query = """
            INSERT INTO products (
                tenant_id, shopify_id, handle, title, body_html, vendor, product_type, tags, status,
                published_at, template_suffix, published_scope, admin_graphql_api_id, min_price,
                max_price, has_discount, options, embedding_json, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        
        values = (
            self.tenant_id,
            product.get('id'),
            product.get('handle'),
            product.get('title'),
            product.get('body_html'),
            product.get('vendor'),
            product.get('product_type'),
            product.get('tags'),
            product.get('status'),
            self.parse_timestamp(product.get('published_at')),
            product.get('template_suffix'),
            product.get('published_scope'),
            product.get('admin_graphql_api_id'),
            computed_fields['min_price'],
            computed_fields['max_price'],
            computed_fields['has_discount'],
            Json(json.loads(computed_fields['options'])),
            Json(embedding_json),  # Add embedding_json as JSONB
            self.parse_timestamp(product.get('created_at')),
            self.parse_timestamp(product.get('updated_at'))
        )
        
        try:
            self.cursor.execute(insert_query, values)
            result = self.cursor.fetchone()
            return result[0] if result else None
        except psycopg2.Error as e:
            print(f"ERROR: Failed to insert product {product.get('id')} ({product.get('title', 'Unknown')})")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Product insertion failed - halting ingestion") from e
    
    def insert_images(self, product_db_id: int, product: Dict[str, Any]) -> Dict[int, int]:
        """Insert all images for a product and return mapping of Shopify image IDs to DB IDs"""
        images = product.get('images', [])
        if not images:
            return {}
        
        shopify_to_db_image_map = {}
        
        insert_query = """
            INSERT INTO product_images (
                product_id, tenant_id, shopify_image_id, shopify_product_id, alt, position,
                width, height, src, admin_graphql_api_id, variant_ids, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, shopify_image_id
        """
        
        for image in images:
            # Convert variant_ids list to PostgreSQL array format
            variant_ids = image.get('variant_ids', [])
            if variant_ids and isinstance(variant_ids, list):
                variant_ids = [int(vid) for vid in variant_ids if vid is not None]
            else:
                variant_ids = []
            
            values = (
                product_db_id,
                self.tenant_id,
                image.get('id'),
                image.get('product_id'),
                image.get('alt'),
                image.get('position'),
                image.get('width'),
                image.get('height'),
                image.get('src'),
                image.get('admin_graphql_api_id'),
                variant_ids,
                self.parse_timestamp(image.get('created_at')),
                self.parse_timestamp(image.get('updated_at'))
            )
            
            try:
                self.cursor.execute(insert_query, values)
                result = self.cursor.fetchone()
                if result:
                    db_image_id, shopify_image_id = result
                    shopify_to_db_image_map[shopify_image_id] = db_image_id
            except psycopg2.Error as e:
                print(f"ERROR: Failed to insert image {image.get('id')} for product {product.get('id')}")
                print(f"Database error: {e}")
                self.conn.rollback()
                raise Exception(f"Image insertion failed - halting ingestion") from e
        
        return shopify_to_db_image_map
    
    def insert_variants(self, product_db_id: int, product: Dict[str, Any], image_map: Dict[int, int] = None):
        """Insert all variants for a product"""
        variants = product.get('variants', [])
        if not variants:
            return
        
        if image_map is None:
            image_map = {}
        
        insert_query = """
            INSERT INTO product_variants (
                product_id, tenant_id, shopify_variant_id, shopify_product_id, title, price, compare_at_price,
                position, inventory_policy, option1, option2, option3, sku, barcode, grams, weight, weight_unit,
                inventory_item_id, inventory_quantity, old_inventory_quantity, inventory_management,
                fulfillment_service, taxable, requires_shipping, admin_graphql_api_id, image_id,
                shopify_image_id, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        variant_values = []
        for variant in variants:
            try:
                price = float(variant['price']) if variant.get('price') else None
                compare_at_price = float(variant['compare_at_price']) if variant.get('compare_at_price') else None
                weight = float(variant['weight']) if variant.get('weight') else None
            except (ValueError, TypeError):
                price = None
                compare_at_price = None
                weight = None
            
            # Get the database image ID from the mapping
            shopify_image_id = variant.get('image_id')
            db_image_id = image_map.get(shopify_image_id) if shopify_image_id else None
            
            values = (
                product_db_id, self.tenant_id, variant.get('id'), variant.get('product_id'), variant.get('title'),
                price, compare_at_price, variant.get('position'), variant.get('inventory_policy'),
                variant.get('option1'), variant.get('option2'), variant.get('option3'),
                variant.get('sku'), variant.get('barcode'), variant.get('grams'), weight, variant.get('weight_unit'),
                variant.get('inventory_item_id'), variant.get('inventory_quantity'), variant.get('old_inventory_quantity'),
                variant.get('inventory_management'), variant.get('fulfillment_service'), variant.get('taxable'),
                variant.get('requires_shipping'), variant.get('admin_graphql_api_id'), db_image_id,
                shopify_image_id, self.parse_timestamp(variant.get('created_at')), self.parse_timestamp(variant.get('updated_at'))
            )
            variant_values.append(values)
        
        try:
            execute_batch(self.cursor, insert_query, variant_values)
        except psycopg2.Error as e:
            print(f"ERROR: Failed to insert variants for product {product.get('id')}")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Variant insertion failed - halting ingestion") from e
    
    # Removed - embedding_text now part of products table
    
    def insert_products(self, products: List[Dict[str, Any]]):
        """Insert a list of Shopify products"""
        total_products = len(products)
        total_variants = sum(len(p.get('variants', [])) for p in products)
        total_images = sum(len(p.get('images', [])) for p in products)
        
        print(f"Starting insertion of {total_products} products with {total_variants} variants and {total_images} images")
        
        successful_products = 0
        failed_products = 0
        
        for i, product in enumerate(products, 1):
            product_db_id = self.insert_product(product)
            
            if product_db_id:
                # Insert images first to get the mapping
                image_map = self.insert_images(product_db_id, product)
                # Then insert variants with the image mapping
                self.insert_variants(product_db_id, product, image_map)
                # Embedding text already inserted with product
                successful_products += 1
                
                if i % 10 == 0:
                    self.conn.commit()
                    print(f"Progress: {i}/{total_products} products")
            else:
                failed_products += 1
        
        # Final commit
        self.conn.commit()
        
        print(f"\nInsertion complete:")
        print(f"  - Successful products: {successful_products}")
        print(f"  - Failed products: {failed_products}")
        print(f"  - Total variants: {total_variants}")
        print(f"  - Total images: {total_images}")
    
    def load_from_file(self, filepath: str):
        """Load and insert products from a JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        if not isinstance(products, list):
            # Handle case where products might be wrapped in an object
            if isinstance(products, dict) and 'products' in products:
                products = products['products']
            else:
                raise ValueError("Expected a list of products or an object with 'products' key")
        
        self.insert_products(products)


def main():
    """Main function to insert products"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Insert Shopify products from JSON file into PostgreSQL')
    parser.add_argument('json_file', help='Path to JSON file containing Shopify products')
    parser.add_argument('--tenant-id', required=True, help='Tenant ID (UUID)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.json_file):
        print(f"Error: File not found: {args.json_file}")
        sys.exit(1)
    
    # Validate tenant_id format
    try:
        uuid.UUID(args.tenant_id)
    except ValueError:
        print(f"Error: Invalid UUID format for tenant_id: {args.tenant_id}")
        sys.exit(1)
    
    # Create inserter instance
    inserter = ProductInserter(tenant_id=args.tenant_id)
    
    try:
        # Connect to database
        inserter.connect()
        
        # Load and insert products
        inserter.load_from_file(args.json_file)
        
        print(f"\nProducts inserted successfully for tenant: {inserter.tenant_id}")
        
    except Exception as e:
        print(f"Error during insertion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        inserter.disconnect()


if __name__ == "__main__":
    main()