"""
Database Connection Pool Manager
Provides efficient connection pooling to avoid creating new connections for every database operation

Note: Currently using psycopg2 with manual connection management.
For production, consider upgrading to psycopg3 with native connection pooling:
pip install psycopg[pool]
"""

import os
from typing import Any, List, Optional, Dict, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager


class Database:
    """
    Database connection pool manager class
    
    Provides connection pooling with tenant isolation and safety features
    """
    
    def __init__(self, dsn: str = None, min_size: int = 2, max_size: int = 10):
        """
        Initialize database connection pool
        
        Args:
            dsn: Database connection string. If None, builds from env vars
            min_size: Minimum number of connections to maintain
            max_size: Maximum connections allowed in pool
        """
        # Build DSN from environment if not provided
        if dsn is None:
            dsn = self._build_dsn_from_env()
        
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool = None
        
        # Initialize the pool
        self._initialize_pool()
    
    def _build_dsn_from_env(self) -> str:
        """Build PostgreSQL DSN from environment variables"""
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME', 'ecom_products')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', '')
        
        return f"host={host} port={port} dbname={database} user={user} password={password}"
    
    def _initialize_pool(self) -> None:
        """Initialize the connection pool"""
        try:
            # Parse DSN into individual components for psycopg2.pool
            # psycopg2.pool doesn't accept DSN strings directly
            config = {}
            for part in self.dsn.split():
                key, value = part.split('=', 1)
                config[key if key != 'dbname' else 'database'] = value
            
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.min_size,
                maxconn=self.max_size,
                **config
            )
            
            print(f"✅ Database connection pool initialized ({self.min_size}-{self.max_size} connections)")
            
        except Exception as e:
            print(f"❌ Failed to initialize connection pool: {e}")
            print(f"   DSN: {self.dsn}")
            self.pool = None
            raise


    def run_read(self, sql: str, params: Tuple = (), tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute a read-only query with optional tenant isolation
        
        This method:
        1. Gets a connection from the pool (reuses existing or creates if needed)
        2. Optionally sets tenant context for Row Level Security
        3. Enforces read-only mode and timeout for safety
        4. Executes query and returns results
        5. Automatically returns connection to pool
        
        Args:
            sql: SQL query to execute (should be SELECT query)
            params: Query parameters for parameterized queries
            tenant_id: Optional UUID of the tenant for RLS isolation
                      If None, no tenant context is set (useful for non-RLS tables)
            
        Returns:
            List of dictionaries representing query results
            
        """
        if self.pool is None:
            raise RuntimeError("Connection pool not initialized")
        
        # Get connection from pool
        conn = self.pool.getconn()
        if conn is None:
            raise RuntimeError("Unable to get connection from pool")
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Start transaction
                cur.execute("BEGIN")
                
                # Set tenant context for Row Level Security (if tenant_id provided)
                if tenant_id is not None:
                    # This ensures queries only see data for this tenant
                    # If table has no RLS policies, this setting is ignored
                    cur.execute("SET LOCAL app.tenant_id = %s", (tenant_id,))
                
                # Safety settings for read operations
                cur.execute("SET LOCAL statement_timeout = '1s'")  # Prevent long-running queries
                cur.execute("SET LOCAL transaction_read_only = on")   # Ensure no writes
                
                # Execute the actual query
                cur.execute(sql, params)
                rows = cur.fetchall()
                
                # Commit to end transaction cleanly
                cur.execute("COMMIT")
                
                # Convert RealDictRow to regular dictionaries
                return [dict(row) for row in rows]
                
        except Exception as e:
            # Rollback on error
            try:
                conn.rollback()
            except:
                pass
            raise e
        finally:
            # Always return connection to pool
            self.pool.putconn(conn)

    def run_write(self, sql: str, params: Tuple = (), tenant_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a write query (INSERT, UPDATE, DELETE) with optional tenant isolation
        
        Args:
            sql: SQL query to execute
            params: Query parameters for parameterized queries  
            tenant_id: Optional UUID of the tenant for RLS isolation
            
        Returns:
            For INSERT with RETURNING: List of dictionaries
            For UPDATE/DELETE: None
        """
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized")
        
        # Get connection from pool
        conn = self.pool.getconn()
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Set tenant context if provided
                if tenant_id:
                    cursor.execute(f"SET myapp.current_tenant = %s", (tenant_id,))
                
                # Execute the write query
                cursor.execute(sql, params)
                
                # Commit the transaction
                conn.commit()
                
                # Return results if query has RETURNING clause
                if cursor.description:
                    return cursor.fetchall()
                return None
                
        except Exception as e:
            # Rollback on error
            conn.rollback()
            raise e
        finally:
            # Always return connection to pool
            self.pool.putconn(conn)

    def close(self):
        """
        Close all connections in the pool
        Call this during application shutdown for clean resource cleanup
        """
        if self.pool:
            try:
                self.pool.closeall()
                print("✅ Database connection pool closed")
            except Exception as e:
                print(f"⚠️ Error closing connection pool: {e}")
            finally:
                self.pool = None
        else:
            print("ℹ️ Connection pool was not initialized or already closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically close pool"""
        self.close()


# Global database instance for backward compatibility
_global_db_instance: Optional[Database] = None


def get_database() -> Database:
    global _global_db_instance
    if _global_db_instance is None:
        _global_db_instance = Database()
    return _global_db_instance


