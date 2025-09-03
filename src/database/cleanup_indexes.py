"""
Script to remove unnecessary indexes identified in the index analysis.
Run this to clean up existing databases that have the old indexes.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def cleanup_indexes():
    """Remove unnecessary indexes from the database"""
    
    # Database connection
    conn_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'ecom_products')
    }
    
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # List of indexes to remove
        indexes_to_drop = [
            # Unused variant indexes
            'idx_variants_tenant',           # No direct queries to variants
            'idx_variants_sku',              # No SKU searches found
            'idx_variants_price',            # Price queries use products table
            'idx_variants_shopify_product_id',  # Not needed if keeping variant_id
            'idx_variants_shopify_image_id',    # Not used in queries
            
            # Unused image indexes  
            'idx_images_shopify_product_id',    # Not used in queries
            'idx_images_product_id',            # Replaced by idx_images_product_position
            
            # Questionable tenant index
            'idx_tenants_name',                 # Lookups use UUID not name
            
            # Unused JSONB index
            'idx_products_options_gin',         # No JSONB queries on options
        ]
        
        dropped_count = 0
        for index_name in indexes_to_drop:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name} CASCADE")
                # Check if index was actually dropped
                cursor.execute("""
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = %s
                """, (index_name,))
                if not cursor.fetchone():
                    print(f"✅ Dropped index: {index_name}")
                    dropped_count += 1
                else:
                    print(f"ℹ️  Index not found: {index_name}")
            except Exception as e:
                print(f"⚠️  Error dropping {index_name}: {e}")
        
        # Add any new optimized indexes that don't exist
        new_indexes = [
            {
                'name': 'idx_products_tenant_id',
                'table': 'products',
                'definition': '(tenant_id, id)',
                'description': 'Composite index for tenant-isolated ID lookups'
            },
            {
                'name': 'idx_products_search_filters',
                'table': 'products', 
                'definition': '(tenant_id, product_type, has_discount, min_price, max_price) INCLUDE (id, title, vendor)',
                'description': 'Covering index for filter searches'
            },
            {
                'name': 'idx_images_product_position',
                'table': 'product_images',
                'definition': '(product_id, position)',
                'description': 'Optimized for fetching primary images'
            }
        ]
        
        added_count = 0
        for index in new_indexes:
            # Check if index already exists
            cursor.execute("""
                SELECT 1 FROM pg_indexes 
                WHERE indexname = %s
            """, (index['name'],))
            
            if not cursor.fetchone():
                try:
                    sql = f"""
                        CREATE INDEX IF NOT EXISTS {index['name']} 
                        ON {index['table']} {index['definition']}
                    """
                    cursor.execute(sql)
                    print(f"✅ Added index: {index['name']} - {index['description']}")
                    added_count += 1
                except Exception as e:
                    print(f"⚠️  Error adding {index['name']}: {e}")
            else:
                print(f"ℹ️  Index already exists: {index['name']}")
        
        conn.commit()
        print(f"\n📊 Summary: Dropped {dropped_count} indexes, added {added_count} indexes")
        
        # Show current index stats
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                COUNT(*) as index_count
            FROM pg_indexes
            WHERE schemaname = 'public'
            GROUP BY schemaname, tablename
            ORDER BY tablename
        """)
        
        print("\n📈 Current index counts by table:")
        for row in cursor.fetchall():
            print(f"  {row['tablename']}: {row['index_count']} indexes")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during cleanup: {e}")
        raise
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("🧹 Starting index cleanup...")
    cleanup_indexes()
    print("✨ Index cleanup complete!")