#!/usr/bin/env python3
"""
Generate embeddings for products that have embedding text but no embeddings
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Optional
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
import uuid
import openai

load_dotenv()


class EmbeddingGenerator:
    def __init__(self, tenant_id: str):
        """Initialize database connection and OpenAI client"""
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
        
        # Initialize OpenAI client for embeddings
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
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
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a batch of texts using OpenAI"""
        if not texts:
            return []
        
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            print(f"Warning: Failed to generate batch embeddings: {e}")
            return [None] * len(texts)
    
    def get_products_without_embeddings(self) -> List[tuple]:
        """Get products that have embedding JSON but no embeddings"""
        query = """
            SELECT id, embedding_json
            FROM products
            WHERE tenant_id = %s 
              AND embedding_json IS NOT NULL 
              AND embedding IS NULL
            ORDER BY id
        """
        
        self.cursor.execute(query, (self.tenant_id,))
        return self.cursor.fetchall()
    
    def insert_embeddings_batch(self, product_texts: List[tuple], batch_size: int = 100):
        """Generate and insert embeddings for products in batches"""
        if not product_texts:
            print("No products need embeddings generated")
            return
        
        print(f"Generating embeddings for {len(product_texts)} products in batches of {batch_size}...")
        
        for i in range(0, len(product_texts), batch_size):
            batch = product_texts[i:i + batch_size]
            batch_jsons = [row[1] for row in batch]  # embedding_json
            batch_product_ids = [row[0] for row in batch]  # product_id
            
            # Convert JSON objects to text strings for embedding
            import json
            batch_texts = [json.dumps(json_obj, ensure_ascii=False) if json_obj else "" for json_obj in batch_jsons]
            
            # Generate embeddings for the batch
            print(f"  Generating embeddings for batch {i//batch_size + 1} ({len(batch_texts)} products)...")
            embeddings = self.generate_embeddings_batch(batch_texts)
            
            # Update products with embeddings
            update_query = """
                UPDATE products
                SET embedding = %s
                WHERE id = %s AND tenant_id = %s
            """
            
            embedding_values = []
            for product_id, embedding_vector in zip(batch_product_ids, embeddings):
                if embedding_vector is not None:
                    embedding_values.append((
                        embedding_vector,
                        product_id,
                        self.tenant_id
                    ))
                else:
                    print(f"Warning: Skipping embedding for product ID {product_id} - generation failed")
            
            if embedding_values:
                try:
                    execute_batch(self.cursor, update_query, embedding_values)
                    print(f"  Updated {len(embedding_values)} product embeddings")
                    self.conn.commit()
                except psycopg2.Error as e:
                    print(f"ERROR: Failed to update batch embeddings")
                    print(f"Database error: {e}")
                    self.conn.rollback()
                    raise Exception(f"Batch embedding update failed") from e
            
            # Add a small delay between batches to be respectful to the API
            if i + batch_size < len(product_texts):
                time.sleep(1)
        
        print(f"\nEmbedding generation complete!")
    
    def generate_all_embeddings(self, batch_size: int = 100):
        """Generate embeddings for all products that need them"""
        # Get products without embeddings
        product_texts = self.get_products_without_embeddings()
        
        if not product_texts:
            print("All products already have embeddings!")
            return
        
        print(f"Found {len(product_texts)} products without embeddings")
        
        # Generate embeddings in batches
        self.insert_embeddings_batch(product_texts, batch_size)
    
    def regenerate_all_embeddings(self, batch_size: int = 100):
        """Regenerate embeddings for ALL products (clear existing first)"""
        print("Regenerating ALL embeddings...")
        
        # Clear existing embeddings for this tenant
        clear_query = "UPDATE products SET embedding = NULL WHERE tenant_id = %s"
        self.cursor.execute(clear_query, (self.tenant_id,))
        cleared_count = self.cursor.rowcount
        self.conn.commit()
        
        print(f"Cleared {cleared_count} existing embeddings")
        
        # Now generate embeddings for all products
        self.generate_all_embeddings(batch_size)


def main():
    """Main function to generate embeddings"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate embeddings for Shopify products')
    parser.add_argument('--tenant-id', required=True, help='Tenant ID (UUID)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for embedding generation (default: 100)')
    parser.add_argument('--regenerate-all', action='store_true',
                       help='Regenerate ALL embeddings (delete existing first)')
    
    args = parser.parse_args()
    
    # Validate tenant_id format
    try:
        uuid.UUID(args.tenant_id)
    except ValueError:
        print(f"Error: Invalid UUID format for tenant_id: {args.tenant_id}")
        sys.exit(1)
    
    # Create generator instance
    generator = EmbeddingGenerator(tenant_id=args.tenant_id)
    
    try:
        # Connect to database
        generator.connect()
        
        # Generate embeddings
        if args.regenerate_all:
            generator.regenerate_all_embeddings(args.batch_size)
        else:
            generator.generate_all_embeddings(args.batch_size)
        
        print(f"\nEmbeddings generated successfully for tenant: {generator.tenant_id}")
        
    except Exception as e:
        print(f"Error during embedding generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        generator.disconnect()


if __name__ == "__main__":
    main()