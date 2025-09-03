"""
Add latency tracking to chat_messages table
"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

def add_latency_column():
    """Add latency column to chat_messages table"""
    
    # Get database connection parameters
    db_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', 5432),
        'database': os.getenv('DB_NAME', 'ecom_products'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD')
    }
    
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Add latency column to chat_messages if it doesn't exist
        cur.execute("""
            ALTER TABLE chat_messages 
            ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
        """)
        
        # Add index for latency queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_latency 
            ON chat_messages(tenant_id, role, latency_ms) 
            WHERE role = 'assistant';
        """)
        
        # Add columns for session-level latency metrics
        cur.execute("""
            ALTER TABLE chat_sessions
            ADD COLUMN IF NOT EXISTS avg_latency_ms INTEGER,
            ADD COLUMN IF NOT EXISTS max_latency_ms INTEGER,
            ADD COLUMN IF NOT EXISTS min_latency_ms INTEGER;
        """)
        
        conn.commit()
        print("✅ Successfully added latency tracking columns")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding latency columns: {e}")
        raise
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    add_latency_column()