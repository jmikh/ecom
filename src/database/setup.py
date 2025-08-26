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
    
    # Drop existing tables if needed (for development - comment out in production)
    cursor.execute("DROP TABLE IF EXISTS attribute_values CASCADE")
    cursor.execute("DROP TABLE IF EXISTS attribute_stats CASCADE")
    cursor.execute("DROP TABLE IF EXISTS product_embeddings CASCADE")
    cursor.execute("DROP TABLE IF EXISTS product_embedding_text CASCADE")
    cursor.execute("DROP TABLE IF EXISTS product_images CASCADE")
    cursor.execute("DROP TABLE IF EXISTS product_variants CASCADE")
    cursor.execute("DROP TABLE IF EXISTS products CASCADE")
    cursor.execute("DROP TABLE IF EXISTS tenants CASCADE")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id BIGSERIAL PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            shopify_id BIGINT UNIQUE,
            handle TEXT,
            title TEXT NOT NULL,
            body_html TEXT,
            vendor TEXT,
            product_type TEXT,
            tags TEXT,
            status TEXT,
            published_at TIMESTAMPTZ,
            template_suffix TEXT,
            published_scope TEXT,
            admin_graphql_api_id TEXT,
            
            -- Computed fields from variants
            min_price NUMERIC(10,2),
            max_price NUMERIC(10,2),
            has_discount BOOLEAN DEFAULT FALSE,
            options JSONB DEFAULT '{}'::jsonb,
            
            -- Timestamps
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id BIGSERIAL PRIMARY KEY,
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            shopify_image_id BIGINT UNIQUE,
            shopify_product_id BIGINT,
            alt TEXT,
            position INT,
            width INT,
            height INT,
            src TEXT,
            admin_graphql_api_id TEXT,
            variant_ids BIGINT[],
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id BIGSERIAL PRIMARY KEY,
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            shopify_variant_id BIGINT UNIQUE,
            shopify_product_id BIGINT,
            title TEXT,
            price NUMERIC(10,2),
            compare_at_price NUMERIC(10,2),
            position INT,
            inventory_policy TEXT,
            option1 TEXT,
            option2 TEXT,
            option3 TEXT,
            sku TEXT,
            barcode TEXT,
            grams INT,
            weight NUMERIC(10,3),
            weight_unit TEXT,
            inventory_item_id BIGINT,
            inventory_quantity INT,
            old_inventory_quantity INT,
            inventory_management TEXT,
            fulfillment_service TEXT,
            taxable BOOLEAN,
            requires_shipping BOOLEAN,
            admin_graphql_api_id TEXT,
            image_id BIGINT REFERENCES product_images(id) ON DELETE SET NULL,
            shopify_image_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_embedding_text (
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            embedding_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, product_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_embeddings (
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            embedding vector(1536),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, product_id)
        )
    """)
    
    # Enable Row Level Security for multi-tenant isolation
    cursor.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_variants ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_images ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_embedding_text ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_embeddings ENABLE ROW LEVEL SECURITY")
    
    # Drop existing policies if exists and recreate (to handle schema changes)
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON products")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_variants")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_images")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_embedding_text")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_embeddings")
    
    cursor.execute("""
        CREATE POLICY tenant_isolation ON products
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    cursor.execute("""
        CREATE POLICY tenant_isolation ON product_variants
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    cursor.execute("""
        CREATE POLICY tenant_isolation ON product_images
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    cursor.execute("""
        CREATE POLICY tenant_isolation ON product_embedding_text
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    cursor.execute("""
        CREATE POLICY tenant_isolation ON product_embeddings
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    
    # Create ANN index for vector similarity search
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_embeddings_vector 
        ON product_embeddings 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # Create essential indexes for the tenants table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenants_name ON tenants (name)")
    
    # Create essential indexes for the products table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tenant ON products (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_shopify_id ON products (shopify_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_product_type ON products (product_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_min_price ON products (min_price)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_max_price ON products (max_price)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_has_discount ON products (has_discount)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_options_gin ON products USING GIN (options jsonb_path_ops)")
    
    # Create essential indexes for product_variants table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_tenant ON product_variants (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_product_id ON product_variants (product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_shopify_variant_id ON product_variants (shopify_variant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_shopify_product_id ON product_variants (shopify_product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_shopify_image_id ON product_variants (shopify_image_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_sku ON product_variants (sku)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_price ON product_variants (price)")
    
    # Create essential indexes for product_images table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_tenant ON product_images (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_product_id ON product_images (product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_shopify_image_id ON product_images (shopify_image_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_shopify_product_id ON product_images (shopify_product_id)")
    
    # Create essential indexes for product_embedding_text table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_text_tenant ON product_embedding_text (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_text_product_id ON product_embedding_text (product_id)")
    
    # Create essential indexes for product_embeddings table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_tenant ON product_embeddings (tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_product_id ON product_embeddings (product_id)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Database tables created successfully")

if __name__ == "__main__":
    setup_database()