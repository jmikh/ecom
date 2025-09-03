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
            description TEXT,
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
            
            -- Embedding fields
            embedding_json JSONB,
            embedding vector(1536),
            
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
    
    # Embedding tables removed - now part of products table
    
    # Enable Row Level Security for multi-tenant isolation
    cursor.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_variants ENABLE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE product_images ENABLE ROW LEVEL SECURITY")
    # Row level security for embedding tables removed - now part of products table
    
    # Drop existing policies if exists and recreate (to handle schema changes)
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON products")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_variants")
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation ON product_images")
    # Policies for embedding tables removed - now part of products table
    
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
    
    # Policies for embedding tables removed - now part of products table
    
    # Create ANN index for vector similarity search on products table
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_embedding_vector 
        ON products 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # ====== PRODUCTS TABLE INDEXES ======
    # Multi-tenant isolation - used in every query
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tenant ON products (tenant_id)")
    
    # Composite index for common ID lookups with tenant isolation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tenant_id ON products (tenant_id, id)")
    
    # Individual filter indexes for search functionality
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_product_type ON products (product_type)")  # Category filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_min_price ON products (min_price)")       # Price range queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_max_price ON products (max_price)")       # Price range queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_has_discount ON products (has_discount)") # Sale items filter
    
    # Composite covering index for filter searches (most common query pattern)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_search_filters 
        ON products (tenant_id, product_type, has_discount, min_price, max_price)
        INCLUDE (id, title, vendor)
    """)
    
    # Shopify sync - keep for product ingestion/updates
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_shopify_id ON products (shopify_id)")
    
    # ====== PRODUCT_VARIANTS TABLE INDEXES ======
    # Only essential indexes - most queries go through products table
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_product_id ON product_variants (product_id)")
    # Shopify sync indexes - keep minimal set for ingestion
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_shopify_variant_id ON product_variants (shopify_variant_id)")
    
    # ====== PRODUCT_IMAGES TABLE INDEXES ======
    # Multi-tenant isolation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_tenant ON product_images (tenant_id)")
    
    # Optimized for fetching primary image (position=1) in product queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_product_position ON product_images (product_id, position)")
    
    # Shopify sync - keep for image updates
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_shopify_image_id ON product_images (shopify_image_id)")
    
    # Indexes for embedding columns now part of products table
    
    # Create chat_sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            session_id VARCHAR(255) NOT NULL,
            started_at TIMESTAMPTZ DEFAULT now(),
            ended_at TIMESTAMPTZ,
            message_count INTEGER DEFAULT 0,
            llm_call_count INTEGER DEFAULT 0,
            total_tokens_used INTEGER DEFAULT 0,
            estimated_cost NUMERIC(10,4) DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            avg_latency_ms INTEGER,
            max_latency_ms INTEGER,
            min_latency_ms INTEGER,
            UNIQUE(tenant_id, session_id)
        )
    """)
    
    # Create chat_messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            session_id VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            intent VARCHAR(100),
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            model_used VARCHAR(100),
            cost NUMERIC(10,6),
            created_at TIMESTAMPTZ DEFAULT now(),
            structured_data JSONB,
            latency_ms INTEGER
        )
    """)
    
    # ====== CHAT TABLES INDEXES ======
    # Session queries - fetch recent sessions for a tenant
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON chat_sessions (tenant_id, started_at DESC)")
    
    # Conversation history - fetch messages for a specific session
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_messages ON chat_messages (tenant_id, session_id, created_at DESC)")
    
    # Recent activity - fetch recent messages across all sessions
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recent_messages ON chat_messages (tenant_id, created_at DESC)")
    
    # Latency analytics - partial index for assistant message performance metrics
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_latency 
        ON chat_messages(tenant_id, role, latency_ms) 
        WHERE role = 'assistant'
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Database tables created successfully")

if __name__ == "__main__":
    setup_database()