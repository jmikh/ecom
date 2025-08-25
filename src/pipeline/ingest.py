import json
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from openai import OpenAI
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ingestion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class ProductIngestor:
    def __init__(self, mock_embeddings=False):
        logger.info("Initializing ProductIngestor...")
        
        # Mock mode flag
        self.mock_embeddings = mock_embeddings
        if self.mock_embeddings:
            logger.warning("⚠️  MOCK MODE ENABLED - Using fake embeddings instead of OpenAI API")
        
        # Database connection
        db_params = {
            'database': os.getenv('DB_NAME', 'ecom_products'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        logger.info(f"Connecting to database: {db_params['user']}@{db_params['host']}:{db_params['port']}/{db_params['database']}")
        
        try:
            self.conn = psycopg2.connect(**db_params)
            self.cursor = self.conn.cursor()
            logger.info("✅ Database connection established")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise
        
        # OpenAI client (only if not in mock mode)
        if not self.mock_embeddings:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key or api_key == 'your-openai-api-key-here':
                logger.error("❌ OpenAI API key not found or not set properly")
                raise ValueError("OpenAI API key is required")
            
            logger.info(f"Initializing OpenAI client with key: {api_key[:10]}...")
            try:
                self.openai_client = OpenAI(api_key=api_key)
                logger.info("✅ OpenAI client initialized")
            except Exception as e:
                logger.error(f"❌ OpenAI client initialization failed: {e}")
                raise
        else:
            self.openai_client = None
            logger.info("✅ Skipped OpenAI client (mock mode)")
        
    def load_products(self, filepath: str = 'products.json') -> List[Dict]:
        logger.info(f"Loading products from {filepath}...")
        try:
            with open(filepath, 'r') as f:
                products = json.load(f)
            logger.info(f"✅ Loaded {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"❌ Failed to load products: {e}")
            raise
    
    def infer_schema(self, products: List[Dict]) -> Dict[str, str]:
        schema = {}
        for product in products:
            for key, value in product.items():
                if key not in schema:
                    if isinstance(value, (int, float)):
                        schema[key] = 'numeric'
                    elif isinstance(value, list):
                        schema[key] = 'array'
                    else:
                        schema[key] = 'text'
        return schema
    
    def insert_products(self, products: List[Dict]):
        logger.info("Inserting products into database...")
        
        try:
            self.cursor.execute("TRUNCATE TABLE products CASCADE")
            logger.info("Truncated existing products table")
            
            insert_query = """
                INSERT INTO products (
                    url, size, price, original_price, review_avg_score,
                    images, options, reviews, material, product_name,
                    material_and_care, about_this_mantra, shipping_and_returns,
                    product_details_fit, category
                ) VALUES %s
                RETURNING id
            """
            
            values = []
            for i, product in enumerate(products):
                logger.debug(f"Processing product {i+1}/{len(products)}: {product.get('product_name', 'Unknown')}")
                values.append((
                    product.get('url'),
                    product.get('size'),
                    product.get('price', 0),
                    product.get('original_price', 0),
                    product.get('review_avg_score', 0),
                    product.get('images', []),
                    product.get('options', []),
                    product.get('reviews', []),
                    product.get('material'),
                    product.get('product_name'),
                    product.get('material_and_care'),
                    product.get('about_this_mantra'),
                    product.get('shipping_and_returns'),
                    product.get('product_details_fit'),
                    product.get('category')
                ))
            
            execute_values(self.cursor, insert_query, values)
            product_ids = self.cursor.fetchall()
            self.conn.commit()
            
            logger.info(f"✅ Inserted {len(product_ids)} products")
            return [pid[0] for pid in product_ids]
        
        except Exception as e:
            logger.error(f"❌ Failed to insert products: {e}")
            self.conn.rollback()
            raise
    
    def update_metadata(self, products: List[Dict]) -> Dict[str, bool]:
        self.cursor.execute("TRUNCATE TABLE metadata")
        
        embedding_fields = {}
        cardinality_threshold = 40
        
        schema = self.infer_schema(products)
        
        for col_name, data_type in schema.items():
            if col_name in ["images", "url"]:
                continue
                
            distinct_values = None
            cardinality = None
            min_val = None
            max_val = None
            is_low_cardinality = False
            has_embeddings = False
            
            if data_type == "numeric":
                # Handle numeric fields like price, rating, etc.
                self.cursor.execute(f"""
                    SELECT MIN({col_name}), MAX({col_name}), COUNT(DISTINCT {col_name})
                    FROM products
                    WHERE {col_name} IS NOT NULL
                """)
                result = self.cursor.fetchone()
                if result:
                    min_val = result[0]
                    max_val = result[1]
                    cardinality = result[2]
                    
            elif data_type == "text":
                self.cursor.execute(f"""
                    SELECT COUNT(DISTINCT {col_name})
                    FROM products
                    WHERE {col_name} IS NOT NULL AND {col_name} != ''
                """)
                cardinality = self.cursor.fetchone()[0]
                
                if cardinality <= cardinality_threshold:
                    self.cursor.execute(f"""
                        SELECT DISTINCT {col_name}
                        FROM products
                        WHERE {col_name} IS NOT NULL AND {col_name} != ''
                    """)
                    distinct = [row[0] for row in self.cursor.fetchall()]
                    distinct_values = distinct
                    is_low_cardinality = True
                else:
                    has_embeddings = True
                    embedding_fields[col_name] = True
                
            elif data_type == 'array':
                self.cursor.execute(f"""
                    SELECT COUNT(DISTINCT elem)
                    FROM products, unnest({col_name}) AS elem
                    WHERE {col_name} IS NOT NULL
                """)
                result = self.cursor.fetchone()
                cardinality = result[0] if result and result[0] else 0
                
                if cardinality <= cardinality_threshold:
                    self.cursor.execute(f"""
                        SELECT DISTINCT elem
                        FROM products, unnest({col_name}) AS elem
                        WHERE {col_name} IS NOT NULL
                    """)
                    distinct = [row[0] for row in self.cursor.fetchall()]
                    distinct_values = distinct
                    is_low_cardinality = True
                else:
                    has_embeddings = True
                    embedding_fields[col_name] = True
            logger.info(f"field {col_name} cardinality is {cardinality}")
                
            self.cursor.execute("""
                INSERT INTO metadata (
                    column_name, data_type, is_low_cardinality, has_embeddings,
                    distinct_values, cardinality, min_value, max_value
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (col_name, data_type, is_low_cardinality, has_embeddings,
                  distinct_values, cardinality, min_val, max_val))
        
        self.conn.commit()
        logger.info(f"✅ Metadata table updated. Fields marked for embeddings: {list(embedding_fields.keys())}")
        return embedding_fields
    
    def generate_embeddings(self, products: List[Dict], product_ids: List[int], embedding_fields: Dict[str, bool]):
        logger.info("Starting embedding generation...")
        logger.info(f"Fields to embed: {list(embedding_fields.keys())}")
        
        try:
            self.cursor.execute("TRUNCATE TABLE embeddings")
            logger.info("Truncated existing embeddings table")
            
            total_embeddings = 0
            api_calls = 0
            batch_size = 100  # Process 100 products per API call
            
            # Process each field separately with batching
            for field in embedding_fields.keys():
                print(embedding_fields[field])
                logger.info(f"🔄 Processing field: {field}")
                
                # Collect ALL texts for this field across ALL products
                field_data = []
                for idx, product in enumerate(products):
                    product_id = product_ids[idx]
                    content = product.get(field)
                    
                    if content:
                        if isinstance(content, list):
                            text = ' '.join([str(item) for item in content if item])
                        else:
                            text = str(content)
                        
                        field_data.append({
                            'product_id': product_id,
                            'text': text[:8000],  # Truncate to OpenAI limit
                            'product_name': product.get('product_name', f'Product {product_id}')
                        })
            
                if not field_data:
                    logger.info(f"  ⚪ No valid content for field '{field}', skipping")
                    continue
                
                logger.info(f"  📊 Found {len(field_data)} products with valid '{field}' content")
                
                # Now batch all texts for this field into groups of 100
                for batch_start in range(0, len(field_data), batch_size):
                    batch_end = min(batch_start + batch_size, len(field_data))
                    batch = field_data[batch_start:batch_end]
                    
                    # Extract just the texts for the API call
                    texts = [item['text'] for item in batch]
                    
                    logger.info(f"  🚀 API call #{api_calls + 1}: Batching {len(texts)} '{field}' texts (batch {batch_start//batch_size + 1}/{(len(field_data)-1)//batch_size + 1})")
                    
                    try:
                        if self.mock_embeddings:
                            # Mock: use zeros for embeddings
                            logger.info(f"  🎭 MOCK: Using zero embeddings for {len(texts)} texts")
                            fake_embedding = [0.0] * 1536
                            embeddings_data = [(batch[i]['product_id'], field, fake_embedding) for i in range(len(texts))]
                            api_calls += 1
                        else:
                            # Real API call
                            response = self.openai_client.embeddings.create(
                                input=texts,
                                model="text-embedding-3-small",
                                dimensions=1536
                            )
                            api_calls += 1
                            
                            # Map embeddings back to products
                            embeddings_data = []
                            for i, embedding_obj in enumerate(response.data):
                                embeddings_data.append((
                                    batch[i]['product_id'],
                                    field,
                                    embedding_obj.embedding
                                ))
                        
                        # Insert batch into database
                        execute_values(
                            self.cursor,
                            """
                            INSERT INTO embeddings (product_id, field, embedding)
                            VALUES %s
                            """,
                            embeddings_data,
                            template="(%s, %s, %s::vector)"
                        )
                        self.conn.commit()
                        
                        total_embeddings += len(embeddings_data)
                        logger.info(f"  ✅ Inserted {len(embeddings_data)} embeddings for '{field}' (total: {total_embeddings})")
                        
                        # Rate limiting between API calls
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing batch for field '{field}': {e}")
                        continue
            
            # Generate combined embeddings
            logger.info("🔄 Processing combined embeddings")
            combined_data = []
            
            for idx, product in enumerate(products):
                product_id = product_ids[idx]
                combined_text = ' '.join([
                    str(product.get('product_name', '')),
                    str(product.get('category', '')),
                    str(product.get('material', '')),
                    str(product.get('about_this_mantra', ''))[:500]
                ]).strip()
                
                if combined_text and len(combined_text) > 20:
                    combined_data.append({
                        'product_id': product_id,
                        'text': combined_text[:8000],
                        'product_name': product.get('product_name', f'Product {product_id}')
                    })
            
            # Process combined embeddings in batches
            for batch_start in range(0, len(combined_data), batch_size):
                batch_end = min(batch_start + batch_size, len(combined_data))
                batch = combined_data[batch_start:batch_end]
                
                texts = [item['text'] for item in batch]
                
                logger.info(f"🚀 API call #{api_calls + 1}: Processing {len(texts)} combined embeddings (batch {batch_start//batch_size + 1})")
                
                try:
                    if self.mock_embeddings:
                        # Mock: use zeros for embeddings
                        logger.info(f"  🎭 MOCK: Using zero embeddings for {len(texts)} combined texts")
                        fake_embedding = [0.0] * 1536
                        embeddings_data = [(batch[i]['product_id'], 'combined', fake_embedding) for i in range(len(texts))]
                        api_calls += 1
                    else:
                        # Real API call
                        response = self.openai_client.embeddings.create(
                            input=texts,
                            model="text-embedding-3-small",
                            dimensions=1536
                        )
                        api_calls += 1
                        
                        embeddings_data = []
                        for i, embedding_obj in enumerate(response.data):
                            embeddings_data.append((
                                batch[i]['product_id'],
                                'combined',
                                embedding_obj.embedding
                            ))
                    
                    execute_values(
                        self.cursor,
                        """
                        INSERT INTO embeddings (product_id, field, embedding)
                        VALUES %s
                        """,
                        embeddings_data,
                        template="(%s, %s, %s::vector)"
                    )
                    self.conn.commit()
                    
                    total_embeddings += len(embeddings_data)
                    logger.info(f"✅ Inserted {len(embeddings_data)} combined embeddings (total: {total_embeddings})")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing combined embeddings batch: {e}")
                    continue
            
            logger.info(f"🎉 Generated {total_embeddings} total embeddings using only {api_calls} API calls!")
            logger.info(f"📈 Efficiency: {total_embeddings/api_calls:.1f} embeddings per API call")
            
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            self.conn.rollback()
            raise
    
    def run_pipeline(self):
        logger.info("🚀 Starting ingestion pipeline...")
        
        try:
            # Load products
            products = self.load_products()
            
            # Infer schema
            logger.info("Inferring data schema...")
            schema = self.infer_schema(products)
            logger.info(f"Inferred schema: {schema}")
            
            # Insert products
            product_ids = self.insert_products(products)
            
            # Update metadata and determine embedding fields
            logger.info("Updating metadata and determining embedding fields...")
            embedding_fields = self.update_metadata(products)
            
            # Generate embeddings
            if embedding_fields:
                logger.info(f"Generating embeddings for {len(embedding_fields)} fields...")
                self.generate_embeddings(products, product_ids, embedding_fields)
            else:
                logger.warning("No fields marked for embeddings")
            
            logger.info("🎉 Ingestion pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Ingestion pipeline failed: {e}")
            raise
        
    def close(self):
        self.cursor.close()
        self.conn.close()

if __name__ == "__main__":
    import sys
    
    # Check for --mock flag
    mock_mode = '--mock' in sys.argv or os.getenv('MOCK_EMBEDDINGS', 'false').lower() == 'true'
    
    ingestor = ProductIngestor(mock_embeddings=mock_mode)
    try:
        ingestor.run_pipeline()
    finally:
        ingestor.close()