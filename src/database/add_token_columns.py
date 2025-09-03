#!/usr/bin/env python3
"""
Add input_tokens and output_tokens columns to chat_sessions table
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_token_columns():
    """Add token columns to chat_sessions table"""
    
    # Database connection parameters
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'ecom_products'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD')
    }
    
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Add columns if they don't exist
        print("Adding token columns to chat_sessions...")
        cursor.execute("""
            ALTER TABLE chat_sessions 
            ADD COLUMN IF NOT EXISTS input_tokens INT DEFAULT 0,
            ADD COLUMN IF NOT EXISTS output_tokens INT DEFAULT 0
        """)
        
        # Update existing sessions with token counts
        print("Updating existing sessions with token counts...")
        cursor.execute("""
            UPDATE chat_sessions cs
            SET 
                input_tokens = COALESCE((
                    SELECT SUM(prompt_tokens) 
                    FROM chat_messages 
                    WHERE tenant_id = cs.tenant_id 
                    AND session_id = cs.session_id
                    AND role = 'assistant'
                ), 0),
                output_tokens = COALESCE((
                    SELECT SUM(completion_tokens) 
                    FROM chat_messages 
                    WHERE tenant_id = cs.tenant_id 
                    AND session_id = cs.session_id
                    AND role = 'assistant'
                ), 0)
        """)
        
        rows_updated = cursor.rowcount
        print(f"✅ Updated {rows_updated} sessions with token counts")
        
        conn.commit()
        print("✅ Migration completed successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_token_columns()