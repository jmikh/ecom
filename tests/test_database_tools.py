"""
Tests for database_tools.py using shopify_products.json test data
"""

import pytest
import json
import os
import uuid
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agent.tools.database_tools import DatabaseTools, SearchProductsInput, DatabaseConnection
from src.database.manage_tenants import TenantManager
from src.pipeline.insert_products import ProductInserter
from src.pipeline.generate_embeddings import EmbeddingGenerator


class TestDatabaseTools:
    """Test suite for DatabaseTools class"""
    
    @classmethod
    def setup_class(cls):
        """Set up test fixtures once for the entire test class"""
        # Use the existing test tenant that already has products
        cls.tenant_id = "6b028cbb-512d-4538-a3b1-71bc40f49ed1"
        cls.tenant_name = "Test Store"
        
        # Check if tenant exists, create if not
        tenant_manager = TenantManager()
        tenant_manager.connect()
        try:
            # Check if tenant exists
            cursor = tenant_manager.cursor
            cursor.execute("SELECT COUNT(*) FROM tenants WHERE tenant_id = %s", (cls.tenant_id,))
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                print(f"Creating test tenant {cls.tenant_id}...")
                tenant_manager.create_tenant(
                    name=cls.tenant_name,
                    description="Test tenant for database tools testing",
                    tenant_id=cls.tenant_id
                )
            else:
                print(f"Using existing test tenant {cls.tenant_id}")
            
            # Check if products exist for this tenant
            cursor.execute("SELECT COUNT(*) FROM products WHERE tenant_id = %s", (cls.tenant_id,))
            product_count = cursor.fetchone()[0]
            
            if product_count == 0:
                # Load and insert test products only if no products exist
                print("Loading test products...")
                with open('shopify_products.json', 'r') as f:
                    cls.products_data = json.load(f)
                
                # Insert products
                inserter = ProductInserter(tenant_id=cls.tenant_id)
                inserter.connect()
                try:
                    inserter.insert_products(cls.products_data)
                finally:
                    inserter.disconnect()
                
                # Generate embeddings for semantic search tests
                print("Generating embeddings (one-time cost)...")
                generator = EmbeddingGenerator(tenant_id=cls.tenant_id)
                generator.connect()
                try:
                    generator.generate_all_embeddings(batch_size=100)
                finally:
                    generator.disconnect()
            else:
                print(f"Using existing {product_count} products for tenant")
        finally:
            tenant_manager.disconnect()
        
        # Initialize DatabaseTools instance
        cls.db_tools = DatabaseTools(tenant_id=cls.tenant_id)
    
    @classmethod
    def teardown_class(cls):
        """Clean up test tenant after all tests"""
        # Don't delete the test tenant - keep it for future test runs
        # This saves on embedding costs
        pass
    
    def test_filters_search_by_product_type(self):
        """Test filtering products by product_type"""
        # From the test data, we know there are Accessories
        filters = {"product_type": "Accessories"}
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        assert len(product_ids) > 0
        assert all(isinstance(pid, int) for pid in product_ids)
        
        # Verify the products actually have the correct type
        products = self.db_tools._get_products_by_ids(product_ids)
        assert all(p['product_type'] == 'Accessories' for p in products)
    
    def test_filters_search_by_vendor(self):
        """Test filtering products by vendor"""
        filters = {"vendor": "United By Blue"}
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        assert len(product_ids) > 0
        
        products = self.db_tools._get_products_by_ids(product_ids)
        assert all(p['vendor'] == 'United By Blue' for p in products)
    
    def test_filters_search_by_price_range(self):
        """Test filtering products by price range"""
        filters = {
            "min_price": 20,
            "max_price": 50
        }
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        
        if product_ids:  # Only check if we have results
            products = self.db_tools._get_products_by_ids(product_ids)
            for product in products:
                assert product['min_price'] <= 50
                assert product['max_price'] >= 20
    
    def test_filters_search_with_multiple_filters(self):
        """Test combining multiple filters"""
        filters = {
            "product_type": "Accessories",
            "max_price": 100
        }
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        
        if product_ids:
            products = self.db_tools._get_products_by_ids(product_ids)
            for product in products:
                assert product['product_type'] == 'Accessories'
                assert product['min_price'] <= 100
    
    def test_filters_search_by_tags(self):
        """Test filtering by tags (partial match)"""
        filters = {"tags": "Accessories"}
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        
        if product_ids:
            products = self.db_tools._get_products_by_ids(product_ids)
            assert all('Accessories' in (p.get('tags', '') or '') for p in products)
    
    def test_semantic_search_basic(self):
        """Test basic semantic search without filters"""
        query = "camping outdoor gear"
        results = self.db_tools._semantic_search(query, limit=5)
        
        assert isinstance(results, list)
        assert all(isinstance(r, tuple) for r in results)
        assert all(len(r) == 2 for r in results)  # (id, score) tuples
        
        if results:
            # Check that scores are floats between 0 and 1
            for product_id, score in results:
                assert isinstance(product_id, int)
                assert isinstance(score, float)
                assert 0 <= score <= 1
    
    def test_semantic_search_with_filter_ids(self):
        """Test semantic search limited to specific product IDs"""
        # First get some product IDs
        filters = {"product_type": "Accessories"}
        filter_ids = self.db_tools._filters_search(filters, limit=10)
        
        # Now do semantic search within those IDs
        query = "hat cap"
        results = self.db_tools._semantic_search(query, limit=5, filter_ids=filter_ids)
        
        assert isinstance(results, list)
        
        if results:
            # Verify all returned IDs were in the filter list
            returned_ids = [r[0] for r in results]
            assert all(pid in filter_ids for pid in returned_ids)
    
    def test_get_products_by_ids_single(self):
        """Test retrieving a single product by ID"""
        # Get one product ID first
        product_ids = self.db_tools._filters_search({}, limit=1)
        assert len(product_ids) == 1
        
        products = self.db_tools._get_products_by_ids(product_ids)
        assert len(products) == 1
        
        product = products[0]
        assert 'id' in product
        assert 'title' in product
        assert 'vendor' in product
        assert 'product_type' in product
        assert 'min_price' in product
        assert 'max_price' in product
    
    def test_get_products_by_ids_multiple(self):
        """Test retrieving multiple products by IDs"""
        product_ids = self.db_tools._filters_search({}, limit=5)
        
        products = self.db_tools._get_products_by_ids(product_ids)
        assert len(products) == len(product_ids)
        
        # Check order is preserved
        for i, product in enumerate(products):
            assert product['id'] == product_ids[i]
    
    def test_get_products_by_ids_empty(self):
        """Test retrieving products with empty ID list"""
        products = self.db_tools._get_products_by_ids([])
        assert products == []
    
    def test_get_products_serialization(self):
        """Test that products are properly serialized"""
        product_ids = self.db_tools._filters_search({}, limit=1)
        products = self.db_tools._get_products_by_ids(product_ids)
        
        product = products[0]
        
        # Check that decimal fields are converted to float
        assert isinstance(product.get('min_price'), (float, type(None)))
        assert isinstance(product.get('max_price'), (float, type(None)))
        
        # Check that internal fields are removed
        assert 'tenant_id' not in product
        assert 'body_html' not in product
        
        # Check that timestamps are ISO strings if present
        for field in ['created_at', 'updated_at', 'published_at']:
            if field in product:
                assert isinstance(product[field], str)
    
    def test_search_products_filters_only(self):
        """Test search_products with only filters"""
        input_data = SearchProductsInput(
            filters={"product_type": "Accessories"},
            k=5
        )
        
        results = self.db_tools.search_products(input_data)
        
        assert isinstance(results, list)
        assert len(results) <= 5
        assert all(p['product_type'] == 'Accessories' for p in results)
        assert all('similarity_score' not in p for p in results)  # No semantic search
    
    def test_search_products_semantic_only(self):
        """Test search_products with only semantic query"""
        input_data = SearchProductsInput(
            semantic_query="outdoor camping gear",
            k=3
        )
        
        results = self.db_tools.search_products(input_data)
        
        assert isinstance(results, list)
        assert len(results) <= 3
        
        # Should have similarity scores
        print("searching for " + input_data.semantic_query)
        print (f"found {len(results)} results")
        for product in results:
            print (product)
            assert 'similarity_score' in product
            assert isinstance(product['similarity_score'], float)
            assert 0 <= product['similarity_score'] <= 1
    
    def test_search_products_combined(self):
        """Test search_products with both filters and semantic query"""
        input_data = SearchProductsInput(
            filters={"product_type": "Accessories"},
            semantic_query="hat cap",
            k=3
        )
        
        results = self.db_tools.search_products(input_data)
        
        assert isinstance(results, list)
        assert len(results) <= 3
        
        # Should have products matching the filter
        assert all(p['product_type'] == 'Accessories' for p in results)
        
        print("searching for " + input_data.semantic_query)
        print (f"found {len(results)} results")
        # Should have similarity scores from semantic search
        for product in results:
            print (product)
            assert 'similarity_score' in product
    
    def test_search_products_respects_limit(self):
        """Test that search_products respects the k parameter"""
        for k in [1, 3, 5, 10]:
            input_data = SearchProductsInput(
                filters={},
                k=k
            )
            
            results = self.db_tools.search_products(input_data)
            assert len(results) <= k
    
    def test_search_products_empty_results(self):
        """Test search_products with filters that return no results"""
        input_data = SearchProductsInput(
            filters={"product_type": "NonexistentType"},
            k=5
        )
        
        results = self.db_tools.search_products(input_data)
        assert results == []
    
    def test_database_connection_context_manager(self):
        """Test that DatabaseConnection properly manages connections"""
        with DatabaseConnection(self.tenant_id) as db:
            assert db.conn is not None
            assert db.cursor is not None
            
            # Test that tenant context is set
            db.cursor.execute("SHOW app.tenant_id")
            result = db.cursor.fetchone()
            assert result['app.tenant_id'] == self.tenant_id
    
    def test_options_filter(self):
        """Test filtering by product options (JSONB)"""
        # This depends on your actual product data having options
        # Example: filtering by size or color
        filters = {"option_Color": "Green"}
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        # Just verify the query runs without error
        assert isinstance(product_ids, list)
    
    @pytest.mark.parametrize("filter_key,filter_value", [
        ("has_discount", True),
        ("has_discount", False),
        ("min_price", 10),
        ("max_price", 200),
    ])
    def test_various_filters(self, filter_key, filter_value):
        """Test various filter types"""
        filters = {filter_key: filter_value}
        product_ids = self.db_tools._filters_search(filters, limit=10)
        
        assert isinstance(product_ids, list)
        # Just verify queries run without errors


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config = MagicMock()
    config.db_host = os.getenv('DB_HOST', 'localhost')
    config.db_port = os.getenv('DB_PORT', '5432')
    config.db_name = os.getenv('DB_NAME', 'ecom_products')
    config.db_user = os.getenv('DB_USER', 'postgres')
    config.db_password = os.getenv('DB_PASSWORD', '')
    config.openai_embedding_model = 'text-embedding-3-small'
    config.openai_api_key = os.getenv('OPENAI_API_KEY')
    return config


def test_search_products_tool():
    """Test the traced tool wrapper"""
    # This would require a running database with test data
    # Included as an example of how to test the tool interface
    pass


if __name__ == "__main__":
    import sys
    from src.database.database_pool import get_database, close_global_database
    
    def main():
        print("🧪 Starting Database Tools Tests...")
        
        # Initialize database connection pool for tests
        try:
            db = get_database()
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Failed to initialize database pool - tests may fail: {e}")
            # Continue anyway - tests will show database connection errors
        
        try:
            # Run tests with pytest
            exit_code = pytest.main([__file__, "-v"])
            sys.exit(exit_code)
        finally:
            # Clean up database pool
            close_global_database()
    
    main()