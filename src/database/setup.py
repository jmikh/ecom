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
            id BIGSERIAL PRIMARY KEY,
            tenant_id UUID NOT NULL,
            sku TEXT NOT NULL,
            title TEXT NOT NULL,
            price NUMERIC(10,2),
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    # Enable Row Level Security for multi-tenant isolation
    cursor.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    
    # Drop existing policy if exists and recreate (to handle schema changes)
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON products")
    cursor.execute("""
        CREATE POLICY tenant_isolation ON products
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    # Create attribute stats table for tracking attribute metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attribute_stats (
            tenant_id UUID,
            key TEXT,
            n_rows INT,
            n_unique INT,
            inferred_type TEXT,
            sample_values JSONB,
            last_updated TIMESTAMPTZ,
            PRIMARY KEY (tenant_id, key)
        )
    """)
    
    # Optional: store full value histograms for low-cardinality keys
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attribute_values (
            tenant_id UUID,
            key TEXT,
            value TEXT,
            freq INT,
            PRIMARY KEY (tenant_id, key, value)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_embeddings (
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL,
            embedding vector(1536),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, product_id)
        )
    """)
    
    # Create ANN index for vector similarity search
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_embeddings_vector 
        ON product_embeddings 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # Create helpful indexes for the products table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tenant ON products (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_attrs_gin ON products USING GIN (attributes jsonb_path_ops)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(tenant_id, sku)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Database tables created successfully")

if __name__ == "__main__":
    setup_database()