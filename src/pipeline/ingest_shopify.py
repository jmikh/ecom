#!/usr/bin/env python3
"""
Ingest Shopify products and variants into PostgreSQL database
"""

import json
import os
import sys
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import execute_batch, Json
from dotenv import load_dotenv
import uuid
import openai
import requests

load_dotenv()


class ShopifyIngestion:
    def __init__(self, tenant_id: str = None):
        """Initialize database connection and tenant ID"""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'ecom_products')
        }
        
        # Generate or use provided tenant_id
        self.tenant_id = tenant_id or str(uuid.uuid4())
        print(f"Using tenant_id: {self.tenant_id}")
        
        self.conn = None
        self.cursor = None
        
        # Initialize OpenAI client for embeddings
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            print("Warning: OPENAI_API_KEY not found. Embeddings will be skipped.")
            self.generate_embeddings = False
        else:
            self.generate_embeddings = True
        
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(**self.conn_params)
        self.cursor = self.conn.cursor()
        
        # Set the tenant context for RLS
        self.cursor.execute("SET app.tenant_id = %s", (self.tenant_id,))
    
    def clean_html(self, html_text: Optional[str]) -> str:
        """
        Extract clean text from HTML content
        
        Args:
            html_text: HTML string to clean
            
        Returns:
            Clean text with HTML tags removed
        """
        if not html_text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_text)
        
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Strip and return
        return text.strip()
    
    def create_embedding_content(self, product: Dict[str, Any]) -> str:
        """
        Create a JSON string containing the fields to embed for a product
        
        Args:
            product: Shopify product data
            
        Returns:
            JSON string with embedding content
        """
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
        
        return json.dumps(embedding_content, ensure_ascii=False)
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a batch of texts using OpenAI
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors (or None for failed embeddings)
        """
        if not self.generate_embeddings or not texts:
            return [None] * len(texts)
        
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            print(f"Warning: Failed to generate batch embeddings: {e}")
            return [None] * len(texts)
    
    def fetch_shopify_products(self, shop_url: str, limit: int = 250) -> List[Dict[str, Any]]:
        """
        Fetch all products from Shopify API with pagination
        
        Args:
            shop_url: Shopify shop URL
            limit: Number of products per page (max 250)
            
        Returns:
            List of all products with their variants
        """
        # Get API credentials from environment
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        api_version = os.getenv('SHOPIFY_API_VERSION', '2024-01')
        
        if not access_token:
            raise ValueError("SHOPIFY_ACCESS_TOKEN must be set in environment variables")
        
        # Build base URL for API calls
        base_url = f"{shop_url.rstrip('/')}/admin/api/{api_version}"
        endpoint = f"{base_url}/products.json"
        
        # Set up headers
        headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
        
        all_products = []
        params = {
            'limit': min(limit, 250),  # Shopify max is 250
            'fields': 'id,title,handle,body_html,vendor,product_type,created_at,updated_at,published_at,tags,status,variants,images,options'
        }
        
        page_info = None
        page_count = 0
        
        print(f"Fetching products from {shop_url}...")
        
        while True:
            # Use page_info for pagination after first request
            if page_info:
                params = {'page_info': page_info, 'limit': params['limit']}
            
            try:
                response = requests.get(endpoint, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    break
                
                all_products.extend(products)
                page_count += 1
                
                print(f"  Fetched page {page_count}: {len(products)} products (Total: {len(all_products)})")
                
                # Check for next page
                link_header = response.headers.get('Link', '')
                page_info = self._extract_page_info(link_header, 'next')
                
                if not page_info:
                    break
                
                # Rate limiting - Shopify allows 2 requests per second
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching products: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response Status: {e.response.status_code}")
                    print(f"Response Body: {e.response.text}")
                raise
        
        print(f"Successfully fetched {len(all_products)} products from Shopify API")
        return all_products
    
    def _extract_page_info(self, link_header: str, rel: str) -> Optional[str]:
        """
        Extract page_info from Link header
        
        Args:
            link_header: The Link header from response
            rel: The relationship type ('next' or 'previous')
            
        Returns:
            page_info value or None
        """
        if not link_header:
            return None
        
        links = link_header.split(',')
        for link in links:
            if f'rel="{rel}"' in link:
                # Extract URL from <url>
                url_match = link.split(';')[0].strip().strip('<>')
                # Extract page_info parameter
                if 'page_info=' in url_match:
                    page_info = url_match.split('page_info=')[1].split('&')[0]
                    return page_info
        
        return None
        
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            
    def compute_product_fields(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute min_price, max_price, has_discount, and options fields from variants
        
        Args:
            product: Raw Shopify product data
            
        Returns:
            Dictionary with computed fields
        """
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
    
    def parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse Shopify timestamp string to datetime"""
        if not timestamp_str:
            return None
        try:
            # Handle Shopify's ISO 8601 format with timezone
            # Example: "2025-08-25T13:07:46-04:00"
            from dateutil import parser
            return parser.parse(timestamp_str)
        except:
            return None
    
    def insert_product(self, product: Dict[str, Any]) -> Optional[int]:
        """
        Insert a single product into the products table
        
        Args:
            product: Shopify product data
            
        Returns:
            The database ID of the inserted product
        """
        computed_fields = self.compute_product_fields(product)
        
        # Delete existing product if it exists (CASCADE will delete variants and images)
        delete_query = "DELETE FROM products WHERE tenant_id = %s AND shopify_id = %s"
        self.cursor.execute(delete_query, (self.tenant_id, product.get('id')))
        
        # Insert fresh
        insert_query = """
            INSERT INTO products (
                tenant_id, shopify_id, handle, title, body_html, vendor, product_type, tags, status,
                published_at, template_suffix, published_scope, admin_graphql_api_id, min_price,
                max_price, has_discount, options, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
        """
        Insert all images for a product and return mapping of Shopify image IDs to DB IDs
        
        Args:
            product_db_id: Database ID of the parent product
            product: Shopify product data containing images
            
        Returns:
            Dictionary mapping Shopify image IDs to database image IDs
        """
        images = product.get('images', [])
        if not images:
            return {}
        
        shopify_to_db_image_map = {}
        
        insert_query = """
            INSERT INTO product_images (
                product_id,
                tenant_id,
                shopify_image_id,
                shopify_product_id,
                alt,
                position,
                width,
                height,
                src,
                admin_graphql_api_id,
                variant_ids,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, shopify_image_id
        """
        
        for image in images:
            # Convert variant_ids list to PostgreSQL array format
            variant_ids = image.get('variant_ids', [])
            if variant_ids and isinstance(variant_ids, list):
                # Ensure all IDs are integers
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
                variant_ids,  # PostgreSQL will handle the array conversion
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
                print(f"ERROR: Failed to insert image {image.get('id')} for product {product.get('id')} ({product.get('title', 'Unknown')})")
                print(f"Database error: {e}")
                self.conn.rollback()
                raise Exception(f"Image insertion failed - halting ingestion") from e
        
        return shopify_to_db_image_map
    
    def insert_variants(self, product_db_id: int, product: Dict[str, Any], image_map: Dict[int, int] = None):
        """
        Insert all variants for a product
        
        Args:
            product_db_id: Database ID of the parent product
            product: Shopify product data containing variants
            image_map: Dictionary mapping Shopify image IDs to database image IDs
        """
        variants = product.get('variants', [])
        if not variants:
            return
        
        if image_map is None:
            image_map = {}
        
        insert_query = """
            INSERT INTO product_variants (
                product_id,
                tenant_id,
                shopify_variant_id,
                shopify_product_id,
                title,
                price,
                compare_at_price,
                position,
                inventory_policy,
                option1,
                option2,
                option3,
                sku,
                barcode,
                grams,
                weight,
                weight_unit,
                inventory_item_id,
                inventory_quantity,
                old_inventory_quantity,
                inventory_management,
                fulfillment_service,
                taxable,
                requires_shipping,
                admin_graphql_api_id,
                image_id,
                shopify_image_id,
                created_at,
                updated_at
            ) VALUES %s
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
                product_db_id,
                self.tenant_id,
                variant.get('id'),
                variant.get('product_id'),
                variant.get('title'),
                price,
                compare_at_price,
                variant.get('position'),
                variant.get('inventory_policy'),
                variant.get('option1'),
                variant.get('option2'),
                variant.get('option3'),
                variant.get('sku'),
                variant.get('barcode'),
                variant.get('grams'),
                weight,
                variant.get('weight_unit'),
                variant.get('inventory_item_id'),
                variant.get('inventory_quantity'),
                variant.get('old_inventory_quantity'),
                variant.get('inventory_management'),
                variant.get('fulfillment_service'),
                variant.get('taxable'),
                variant.get('requires_shipping'),
                variant.get('admin_graphql_api_id'),
                db_image_id,  # Use the mapped database ID
                shopify_image_id,  # Also store the original Shopify image ID
                self.parse_timestamp(variant.get('created_at')),
                self.parse_timestamp(variant.get('updated_at'))
            )
            variant_values.append(values)
        
        try:
            execute_batch(self.cursor, insert_query, variant_values, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
        except psycopg2.Error as e:
            print(f"ERROR: Failed to insert variants for product {product.get('id')} ({product.get('title', 'Unknown')})")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Variant insertion failed - halting ingestion") from e
    
    def insert_embedding_text(self, product_db_id: int, product: Dict[str, Any]):
        """
        Insert embedding text for a product (for debugging)
        
        Args:
            product_db_id: Database ID of the product
            product: Shopify product data
        """
        # Create embedding content
        embedding_text = self.create_embedding_content(product)
        
        # Insert embedding text
        insert_query = """
            INSERT INTO product_embedding_text (
                product_id,
                tenant_id,
                embedding_text,
                created_at
            ) VALUES (%s, %s, %s, %s)
        """
        
        try:
            self.cursor.execute(insert_query, (
                product_db_id,
                self.tenant_id,
                embedding_text,
                datetime.now()
            ))
        except psycopg2.Error as e:
            print(f"ERROR: Failed to insert embedding text for product {product.get('id')} ({product.get('title', 'Unknown')})")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Embedding text insertion failed - halting ingestion") from e
    
    def insert_embeddings_batch(self, products_data: List[Dict[str, Any]], batch_size: int = 100):
        """
        Generate and insert embeddings for a batch of products
        
        Args:
            products_data: List of tuples containing (product_db_id, product_data)
            batch_size: Number of embeddings to generate per API call
        """
        if not self.generate_embeddings or not products_data:
            return
        
        print(f"Generating embeddings in batches of {batch_size}...")
        
        # Get all product IDs
        product_ids = [product_db_id for product_db_id, _ in products_data]
        
        for i in range(0, len(product_ids), batch_size):
            batch_product_ids = product_ids[i:i + batch_size]
            
            # Fetch embedding texts from database
            fetch_query = """
                SELECT product_id, embedding_text 
                FROM product_embedding_text 
                WHERE tenant_id = %s AND product_id = ANY(%s)
                ORDER BY product_id
            """
            
            self.cursor.execute(fetch_query, (self.tenant_id, batch_product_ids))
            text_results = self.cursor.fetchall()
            
            if not text_results:
                print(f"  Warning: No embedding texts found for batch {i//batch_size + 1}")
                continue
            
            batch_texts = [row[1] for row in text_results]
            batch_product_ids = [row[0] for row in text_results]
            
            # Generate embeddings for the batch
            print(f"  Generating embeddings for batch {i//batch_size + 1} ({len(batch_texts)} products)...")
            embeddings = self.generate_embeddings_batch(batch_texts)
            
            # Insert embeddings
            insert_query = """
                INSERT INTO product_embeddings (
                    product_id,
                    tenant_id,
                    embedding,
                    updated_at
                ) VALUES (%s, %s, %s, %s)
            """
            
            embedding_values = []
            for product_db_id, embedding_vector in zip(batch_product_ids, embeddings):
                if embedding_vector is not None:
                    embedding_values.append((
                        product_db_id,
                        self.tenant_id,
                        embedding_vector,
                        datetime.now()
                    ))
                else:
                    print(f"Warning: Skipping embedding for product ID {product_db_id} - generation failed")
            
            if embedding_values:
                try:
                    execute_batch(self.cursor, insert_query, embedding_values)
                    print(f"  Inserted {len(embedding_values)} embeddings")
                except psycopg2.Error as e:
                    print(f"ERROR: Failed to insert batch embeddings")
                    print(f"Database error: {e}")
                    self.conn.rollback()
                    raise Exception(f"Batch embedding insertion failed - halting ingestion") from e
            
            # Add a small delay between batches to be respectful to the API
            if i + batch_size < len(products_data):
                import time
                time.sleep(1)
    
    def ingest_products(self, products: List[Dict[str, Any]]):
        """
        Ingest a list of Shopify products
        
        Args:
            products: List of Shopify product data
        """
        total_products = len(products)
        total_variants = sum(len(p.get('variants', [])) for p in products)
        total_images = sum(len(p.get('images', [])) for p in products)
        
        embeddings_status = "enabled" if self.generate_embeddings else "disabled"
        print(f"Starting ingestion of {total_products} products with {total_variants} variants, {total_images} images (embeddings: {embeddings_status})")
        
        successful_products = 0
        failed_products = 0
        products_for_embeddings = []  # Store (product_db_id, product_data) for batch embedding
        
        print("Phase 1: Inserting products, variants, and images...")
        for i, product in enumerate(products, 1):
            product_db_id = self.insert_product(product)
            
            if product_db_id:
                # Insert images first to get the mapping
                image_map = self.insert_images(product_db_id, product)
                # Then insert variants with the image mapping
                self.insert_variants(product_db_id, product, image_map)
                # Insert embedding text during product ingestion
                self.insert_embedding_text(product_db_id, product)
                # Store for batch embedding generation
                products_for_embeddings.append((product_db_id, product))
                successful_products += 1
                
                if i % 10 == 0:
                    self.conn.commit()
                    print(f"Progress: {i}/{total_products} products")
            else:
                failed_products += 1
        
        # Commit after products/variants/images
        self.conn.commit()
        
        # Phase 2: Generate embeddings in batches
        if self.generate_embeddings and products_for_embeddings:
            print(f"\nPhase 2: Generating embeddings for {len(products_for_embeddings)} products...")
            # Pass batch_size parameter (will be set in main function)
            self.insert_embeddings_batch(products_for_embeddings, getattr(self, 'embedding_batch_size', 100))
            self.conn.commit()
        
        print(f"\nIngestion complete:")
        print(f"  - Successful products: {successful_products}")
        print(f"  - Failed products: {failed_products}")
        print(f"  - Total variants: {total_variants}")
        print(f"  - Total images: {total_images}")
        if self.generate_embeddings:
            print(f"  - Embeddings generated: {successful_products}")
        else:
            print(f"  - Embeddings: skipped (no OpenAI API key)")
    
    def load_from_file(self, filepath: str):
        """Load and ingest products from a JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        if not isinstance(products, list):
            # Handle case where products might be wrapped in an object
            if isinstance(products, dict) and 'products' in products:
                products = products['products']
            else:
                raise ValueError("Expected a list of products or an object with 'products' key")
        
        self.ingest_products(products)


def main():
    """Main function to run ingestion - orchestrates fetch, insert, and embedding generation"""
    import argparse
    import subprocess
    
    parser = argparse.ArgumentParser(description='Ingest Shopify products into PostgreSQL - orchestrates all steps')
    
    # Operation modes
    parser.add_argument('--fetch-only', action='store_true',
                       help='Only fetch products from Shopify to JSON file')
    parser.add_argument('--insert-only', action='store_true',
                       help='Only insert products from JSON file to database')
    parser.add_argument('--embeddings-only', action='store_true',
                       help='Only generate embeddings for existing products')
    
    # Input/output
    parser.add_argument('--shopify-url', help='Shopify store URL (required for --fetch-only or full pipeline)')
    parser.add_argument('--json-file', help='JSON file path (input for insert, output for fetch)')
    
    # Required parameters
    parser.add_argument('--tenant-id', required=True, help='Tenant ID (UUID)')
    
    # Optional parameters
    parser.add_argument('--embedding-batch-size', type=int, default=100,
                       help='Batch size for embedding generation (default: 100)')
    parser.add_argument('--regenerate-embeddings', action='store_true',
                       help='Regenerate ALL embeddings (delete existing first)')
    
    args = parser.parse_args()
    
    operation_modes = sum([args.fetch_only, args.insert_only, args.embeddings_only])
    
    # Set default behavior if no specific mode is chosen
    if operation_modes == 0:
        print("Running full pipeline: fetch → insert → embeddings")
        fetch_step = True
        insert_step = True
        embeddings_step = True
    else:
        fetch_step = args.fetch_only
        insert_step = args.insert_only
        embeddings_step = args.embeddings_only
    
    # Validate required parameters for each operation
    if fetch_step:
        if not args.shopify_url:
            print("Error: --shopify-url is required for fetching products")
            sys.exit(1)
        if not args.json_file:
            print("Error: --json-file is required to specify output file for writing fetched products")
            sys.exit(1)
    
    if insert_step:
        if not args.json_file:
            print("Error: --json-file is required to products from into the database")
            sys.exit(1)
    
    # Validate tenant_id format
    try:
        uuid.UUID(args.tenant_id)
    except ValueError:
        print(f"Error: Invalid UUID format for tenant_id: {args.tenant_id}")
        sys.exit(1)
    
    # Generate filenames if needed
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # Step 1: Fetch products from Shopify
        if fetch_step:
            print("\n=== STEP 1: Fetching products from Shopify ===")
            fetch_script = os.path.join(script_dir, 'fetch_products.py')
            cmd = [sys.executable, fetch_script, args.shopify_url, args.json_file]
            subprocess.run(cmd, check=True)
            print("✓ Fetch completed successfully")
        
        # Step 2: Insert products into database
        if insert_step:
            print(f"\n=== STEP 2: Inserting products into database ===")
            insert_script = os.path.join(script_dir, 'insert_products.py')
            cmd = [sys.executable, insert_script, args.json_file, '--tenant-id', args.tenant_id]
            subprocess.run(cmd, check=True)
            print("✓ Insert completed successfully")
        
        # Step 3: Generate embeddings
        if embeddings_step:
            print(f"\n=== STEP 3: Generating embeddings ===")
            embeddings_script = os.path.join(script_dir, 'generate_embeddings.py')
            cmd = [sys.executable, embeddings_script, '--tenant-id', args.tenant_id, '--batch-size', str(args.embedding_batch_size)]
            if args.regenerate_embeddings:
                cmd.append('--regenerate-all')
            subprocess.run(cmd, check=True)
            print("✓ Embeddings completed successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"\nError: Step failed with exit code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during pipeline execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()