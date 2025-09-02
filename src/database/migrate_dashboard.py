#!/usr/bin/env python3
"""
Database migration script for dashboard features
Adds new columns to tenants table and creates analytics tables
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "ecom_products"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

def migrate_tenant_table(cursor):
    """Add new columns to tenants table"""
    print("📊 Updating tenants table...")
    
    # Check which columns already exist
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'tenants'
    """)
    existing_columns = [row[0] for row in cursor.fetchall()]
    
    # Add new columns if they don't exist
    if 'brand_voice' not in existing_columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN brand_voice TEXT")
        print("  ✅ Added brand_voice column")
    
    if 'store_url' not in existing_columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN store_url VARCHAR(255)")
        print("  ✅ Added store_url column")
    
    if 'logo_url' not in existing_columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN logo_url TEXT")
        print("  ✅ Added logo_url column")
    
    if 'settings' not in existing_columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN settings JSONB DEFAULT '{}'::jsonb")
        print("  ✅ Added settings column")

def create_analytics_tables(cursor):
    """Create analytics tables for dashboard"""
    print("\n📈 Creating analytics tables...")
    
    # Chat sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            session_id VARCHAR(255) NOT NULL,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            ended_at TIMESTAMPTZ,
            message_count INT DEFAULT 0,
            llm_call_count INT DEFAULT 0,
            total_tokens_used INT DEFAULT 0,
            estimated_cost DECIMAL(10,4) DEFAULT 0,
            UNIQUE(tenant_id, session_id)
        )
    """)
    print("  ✅ Created chat_sessions table")
    
    # Create indexes for sessions
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_tenant 
        ON chat_sessions(tenant_id, started_at DESC)
    """)
    
    # Chat messages table (replaces Redis for conversation history)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            session_id VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            intent VARCHAR(100),
            prompt_tokens INT,
            completion_tokens INT,
            total_tokens INT,
            model_used VARCHAR(100),
            cost DECIMAL(10,6),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ Created chat_messages table")
    
    # Create indexes for fast message retrieval
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_messages 
        ON chat_messages(tenant_id, session_id, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_recent_messages 
        ON chat_messages(tenant_id, created_at DESC)
    """)
    
    # Product analytics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_analytics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            session_id VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ Created product_analytics table")
    
    # Create indexes for product analytics
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_events 
        ON product_analytics(tenant_id, product_id, event_type, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_events_by_session 
        ON product_analytics(tenant_id, session_id, created_at DESC)
    """)

def verify_migration(cursor):
    """Verify that migration was successful"""
    print("\n🔍 Verifying migration...")
    
    # Check tenants table columns
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tenants' 
        AND column_name IN ('brand_voice', 'store_url', 'logo_url', 'settings')
    """)
    tenant_columns = cursor.fetchall()
    print(f"  ✓ Tenant table has {len(tenant_columns)} new columns")
    
    # Check analytics tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('chat_sessions', 'chat_messages', 'product_analytics')
    """)
    analytics_tables = cursor.fetchall()
    print(f"  ✓ Created {len(analytics_tables)} analytics tables")
    
    return len(tenant_columns) == 4 and len(analytics_tables) == 3

def main():
    """Run the migration"""
    print("🚀 Starting Dashboard Migration")
    print("=" * 50)
    
    conn = None
    try:
        # Connect to database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Run migrations
        migrate_tenant_table(cursor)
        create_analytics_tables(cursor)
        
        # Verify and commit
        if verify_migration(cursor):
            conn.commit()
            print("\n✅ Migration completed successfully!")
        else:
            conn.rollback()
            print("\n❌ Migration verification failed, rolled back")
            sys.exit(1)
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main()