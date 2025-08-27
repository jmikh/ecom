#!/usr/bin/env python3
"""
Demonstrate the agent's thinking process with different query types
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_agent_with_logging import LoggingProductAgent

async def demo_agent_thinking():
    TENANT_ID = "75a3f9b9-effc-4e9f-a829-5cdda2ec729d"
    
    print("🤖 LangGraph Product Agent - Thinking Process Demo")
    print("=" * 60)
    
    try:
        agent = LoggingProductAgent(tenant_id=TENANT_ID)
        
        # Test queries that showcase different thinking patterns
        test_queries = [
            ("💰 SQL Price Filter", "Show me products under $30"),
            ("🔍 Semantic Search", "Find me comfortable accessories"),  
            ("🎯 Combined Filters", "Outdoor gear under $100"),
            ("❓ Memory Context", "Tell me more about the first one")
        ]
        
        for category, query in test_queries:
            print(f"\n{'='*60}")
            print(f"{category}: {query}")
            print(f"{'='*60}")
            
            response = await agent.chat_with_logging(query)
            print(f"\n🤖 FINAL RESPONSE:\n{response}")
            
            # Add small delay between queries
            await asyncio.sleep(1)
        
        print(f"\n{'='*60}")
        print("✅ Demo completed! Check agent_thinking.log for full details")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_agent_thinking())