#!/usr/bin/env python3
"""
Test script for LangGraph Product Agent
"""

import asyncio
from src.agent import ProductAgent
from src.agent.memory import SessionManager

async def test_agent():
    """Test the agent with various queries"""
    
    # Replace with your actual tenant ID
    TENANT_ID = "75a3f9b9-effc-4e9f-a829-5cdda2ec729d"
    
    print("🤖 Initializing Product Recommendation Agent...")
    agent = ProductAgent(tenant_id=TENANT_ID)
    
    # Test queries
    test_queries = [
        "Show me some products under $50",
        "I'm looking for jewelry",
        "What discounted items do you have?",
        "Tell me more about the first product",
        "Find similar products to that one"
    ]
    
    print(f"\n📊 Testing with tenant: {TENANT_ID}")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n👤 User [{i}]: {query}")
        print("-" * 40)
        
        try:
            response = await agent.chat(query)
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("=" * 60)
    
    # Show session summary
    session_manager = SessionManager()
    session_data = session_manager.get_session_data(agent.session_id, TENANT_ID)
    
    if session_data:
        print("\n📝 Session Summary:")
        print(f"  - Session ID: {agent.session_id}")
        print(f"  - Search History: {len(session_data.get('search_history', []))} searches")
        print(f"  - Viewed Products: {len(session_data.get('viewed_products', []))} products")
    
    print("\n✅ Test completed!")


async def test_direct_tools():
    """Test database tools directly"""
    from src.agent.tools import DatabaseTools
    
    TENANT_ID = "75a3f9b9-effc-4e9f-a829-5cdda2ec729d"
    
    print("🔧 Testing Database Tools...")
    db_tools = DatabaseTools(tenant_id=TENANT_ID)
    
    # Test schema info
    print("\n1️⃣ Schema Information:")
    schema = db_tools.get_schema_info()
    print(f"  - Total Products: {schema['total_products']}")
    print(f"  - Product Types: {schema['product_types'][:5]}...")
    print(f"  - Price Range: ${schema['price_range']['min']:.2f} - ${schema['price_range']['max']:.2f}")
    
    # Test SQL search
    print("\n2️⃣ SQL Search (products under $100):")
    sql_results = db_tools.sql_search({"max_price": 100}, limit=5)
    for product in sql_results[:3]:
        print(f"  - {product['title']}: ${product.get('min_price', 0):.2f}")
    
    # Test semantic search
    print("\n3️⃣ Semantic Search (jewelry):")
    semantic_results = db_tools.semantic_search("jewelry", limit=5)
    for product in semantic_results[:3]:
        print(f"  - {product['title']} (similarity: {product.get('similarity_score', 0):.2f})")
    
    print("\n✅ Tools test completed!")


def main():
    """Main entry point"""
    import sys
    from src.database.database_pool import get_database, close_global_database
    
    print("""
╔════════════════════════════════════════╗
║  LangGraph Product Agent Test Suite   ║
╚════════════════════════════════════════╝
    """)
    
    # Initialize database connection pool
    print("🚀 Initializing database connection pool...")
    try:
        db = get_database()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to initialize database pool - tests may fail: {e}")
        # Continue anyway - let tests show what fails
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--tools":
            # Test tools directly
            asyncio.run(test_direct_tools())
        else:
            # Test full agent
            asyncio.run(test_agent())
    finally:
        # Clean up database pool
        close_global_database()


if __name__ == "__main__":
    main()