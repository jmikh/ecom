#!/usr/bin/env python3
"""
Manage tenants in the database - create, list, delete tenants
"""

import os
import sys
import uuid
from typing import Optional
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class TenantManager:
    def __init__(self):
        """Initialize database connection"""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'ecom_products')
        }
        
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(**self.conn_params)
        self.cursor = self.conn.cursor()
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def create_tenant(self, name: str, tenant_id: Optional[str] = None) -> str:
        """
        Create a new tenant
        
        Args:
            name: Human-readable name for the tenant
            tenant_id: Optional UUID string, will generate if not provided
            
        Returns:
            The tenant UUID that was created
        """
        if tenant_id:
            # Validate provided UUID
            try:
                uuid.UUID(tenant_id)
            except ValueError:
                raise ValueError(f"Invalid UUID format: {tenant_id}")
        else:
            # Generate new UUID
            tenant_id = str(uuid.uuid4())
        
        # Check if tenant already exists
        check_query = "SELECT name FROM tenants WHERE tenant_id = %s"
        self.cursor.execute(check_query, (tenant_id,))
        
        if self.cursor.fetchone():
            raise ValueError(f"Tenant with ID {tenant_id} already exists")
        
        # Insert new tenant
        insert_query = """
            INSERT INTO tenants (tenant_id, name) 
            VALUES (%s, %s)
        """
        
        try:
            self.cursor.execute(insert_query, (tenant_id, name))
            self.conn.commit()
            print(f"✓ Created tenant: {name} ({tenant_id})")
            return tenant_id
        except psycopg2.Error as e:
            print(f"ERROR: Failed to create tenant")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Tenant creation failed") from e
    
    def list_tenants(self):
        """List all tenants"""
        query = "SELECT tenant_id, name, created_at FROM tenants ORDER BY created_at"
        self.cursor.execute(query)
        tenants = self.cursor.fetchall()
        
        if not tenants:
            print("No tenants found")
            return
        
        print(f"{'Tenant ID':<40} {'Name':<20} {'Created'}")
        print("-" * 80)
        for tenant_id, name, created_at in tenants:
            created_str = created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else 'Unknown'
            print(f"{tenant_id:<40} {name:<20} {created_str}")
    
    def delete_tenant(self, tenant_id: str, force: bool = False):
        """
        Delete a tenant (WARNING: This will delete ALL associated data)
        
        Args:
            tenant_id: UUID of tenant to delete
            force: If True, skip confirmation prompt
        """
        # Validate UUID format
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {tenant_id}")
        
        # Check if tenant exists and get info
        check_query = "SELECT name FROM tenants WHERE tenant_id = %s"
        self.cursor.execute(check_query, (tenant_id,))
        result = self.cursor.fetchone()
        
        if not result:
            print(f"Tenant {tenant_id} not found")
            return
        
        tenant_name = result[0]
        
        # Get count of associated data
        count_query = "SELECT COUNT(*) FROM products WHERE tenant_id = %s"
        self.cursor.execute(count_query, (tenant_id,))
        product_count = self.cursor.fetchone()[0]
        
        if not force:
            print(f"WARNING: This will delete tenant '{tenant_name}' ({tenant_id})")
            print(f"This will also delete {product_count} associated products and ALL related data")
            confirm = input("Are you sure? (type 'DELETE' to confirm): ")
            if confirm != 'DELETE':
                print("Deletion cancelled")
                return
        
        # Delete tenant (CASCADE will handle all related data)
        delete_query = "DELETE FROM tenants WHERE tenant_id = %s"
        
        try:
            self.cursor.execute(delete_query, (tenant_id,))
            self.conn.commit()
            print(f"✓ Deleted tenant: {tenant_name} ({tenant_id})")
            print(f"✓ Deleted {product_count} associated products and related data")
        except psycopg2.Error as e:
            print(f"ERROR: Failed to delete tenant")
            print(f"Database error: {e}")
            self.conn.rollback()
            raise Exception(f"Tenant deletion failed") from e


def main():
    """Main function for tenant management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Manage tenants in the e-commerce database')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create tenant command
    create_parser = subparsers.add_parser('create', help='Create a new tenant')
    create_parser.add_argument('name', help='Human-readable name for the tenant')
    create_parser.add_argument('--tenant-id', help='Optional UUID for tenant (will generate if not provided)')
    
    # List tenants command
    list_parser = subparsers.add_parser('list', help='List all tenants')
    
    # Delete tenant command
    delete_parser = subparsers.add_parser('delete', help='Delete a tenant (WARNING: Deletes all data)')
    delete_parser.add_argument('tenant_id', help='UUID of tenant to delete')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    manager = TenantManager()
    
    try:
        manager.connect()
        
        if args.command == 'create':
            tenant_id = manager.create_tenant(args.name, args.tenant_id)
            
        elif args.command == 'list':
            manager.list_tenants()
            
        elif args.command == 'delete':
            manager.delete_tenant(args.tenant_id, args.force)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        manager.disconnect()


if __name__ == "__main__":
    main()