#!/usr/bin/env python3

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

def inspect_database():
    # Connect to database
    conn_params = {
        'database': os.getenv('DB_NAME', 'ecom_products'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'cursor_factory': RealDictCursor
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("DATABASE INSPECTION REPORT")
        print("=" * 80)
        print(f"Database: {conn_params['database']}")
        print(f"Host: {conn_params['host']}:{conn_params['port']}")
        print(f"User: {conn_params['user']}")
        print()
        
        # Check if tables exist
        print("📋 TABLES:")
        cursor.execute("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        for table in tables:
            print(f"  • {table['table_name']} ({table['table_type']})")
        print()
        
        # Check if pgvector extension is installed
        print("🧮 EXTENSIONS:")
        cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
        vector_ext = cursor.fetchone()
        if vector_ext:
            print(f"  ✅ pgvector installed (version {vector_ext.get('extversion', 'unknown')})")
        else:
            print("  ❌ pgvector not installed")
        print()
        
        # Products table inspection
        if any(t['table_name'] == 'products' for t in tables):
            print("📦 PRODUCTS TABLE:")
            cursor.execute("SELECT COUNT(*) as count FROM products")
            count = cursor.fetchone()['count']
            print(f"  Total products: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM products LIMIT 1")
                sample = cursor.fetchone()
                print("  Sample product fields:")
                for key, value in sample.items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    elif isinstance(value, list) and len(value) > 3:
                        value = value[:3] + ["..."]
                    print(f"    {key}: {value}")
            print()
        
        # Metadata table inspection
        if any(t['table_name'] == 'metadata' for t in tables):
            print("📊 METADATA TABLE:")
            cursor.execute("SELECT COUNT(*) as count FROM metadata")
            count = cursor.fetchone()['count']
            print(f"  Total metadata entries: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM metadata ORDER BY column_name")
                metadata = cursor.fetchall()
                print("  Column analysis:")
                for row in metadata:
                    embed_status = "🔄" if row['has_embeddings'] else "⚪"
                    print(f"    {embed_status} {row['column_name']} ({row['data_type']}) - {row['cardinality']} unique values")
                    if row['distinct_values']:
                        values = row['distinct_values'][:5]
                        if len(row['distinct_values']) > 5:
                            values.append("...")
                        print(f"        Values: {values}")
            print()
        
        # Embeddings table inspection
        if any(t['table_name'] == 'embeddings' for t in tables):
            print("🧠 EMBEDDINGS TABLE:")
            cursor.execute("SELECT COUNT(*) as count FROM embeddings")
            count = cursor.fetchone()['count']
            print(f"  Total embeddings: {count}")
            
            if count > 0:
                cursor.execute("""
                    SELECT field, COUNT(*) as count 
                    FROM embeddings 
                    GROUP BY field 
                    ORDER BY count DESC
                """)
                field_counts = cursor.fetchall()
                print("  Embeddings by field:")
                for row in field_counts:
                    print(f"    {row['field']}: {row['count']} embeddings")
                
                cursor.execute("SELECT array_length(embedding, 1) as dimensions FROM embeddings LIMIT 1")
                dims = cursor.fetchone()
                if dims:
                    print(f"  Embedding dimensions: {dims['dimensions']}")
            print()
        
        # Database size
        print("💾 DATABASE SIZE:")
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """)
        sizes = cursor.fetchall()
        for row in sizes:
            print(f"  {row['tablename']}: {row['size']}")
        print()
        
        cursor.close()
        conn.close()
        
        print("=" * 80)
        print("INSPECTION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")
        return False
    
    return True

def quick_query(query: str):
    """Execute a quick SQL query for manual inspection"""
    conn_params = {
        'database': os.getenv('DB_NAME', 'ecom_products'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'cursor_factory': RealDictCursor
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"\nQuery: {query}")
        print("-" * 40)
        for row in results:
            pprint(dict(row))
        print()
        
    except Exception as e:
        print(f"❌ Query failed: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Execute custom query
        query = " ".join(sys.argv[1:])
        quick_query(query)
    else:
        # Run full inspection
        inspect_database()