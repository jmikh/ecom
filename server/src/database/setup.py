import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': 'postgres'  # Connect to postgres db first
    }
    
    conn = psycopg2.connect(**conn_params)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    db_name = os.getenv('DB_NAME', 'ecom_products')
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"Database {db_name} created successfully")
    
    cursor.close()
    conn.close()
    
    conn_params['database'] = db_name
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor()
    
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    print("pgvector extension enabled")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            url TEXT,
            size TEXT,
            price DECIMAL(10, 2),
            original_price DECIMAL(10, 2),
            review_avg_score DECIMAL(3, 2),
            images TEXT[],
            options TEXT[],
            reviews TEXT[],
            material TEXT,
            product_name TEXT,
            material_and_care TEXT,
            about_this_mantra TEXT,
            shipping_and_returns TEXT,
            product_details_fit TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            id SERIAL PRIMARY KEY,
            column_name TEXT UNIQUE,
            data_type TEXT,
            is_low_cardinality BOOLEAN,
            has_embeddings BOOLEAN DEFAULT FALSE,
            distinct_values TEXT[],
            cardinality INTEGER,
            min_value TEXT,
            max_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            field TEXT,
            embedding vector(1536),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, field)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_review_score ON products(review_avg_score)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Database tables created successfully")

if __name__ == "__main__":
    setup_database()