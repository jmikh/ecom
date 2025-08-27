#!/usr/bin/env python3
"""
Quick test of semantic search fix
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_agent_with_logging import LoggingProductAgent

async def test_semantic_search():
    TENANT_ID = "75a3f9b9-effc-4e9f-a829-5cdda2ec729d"
    
    try:
        print("🔧 Testing semantic search fix...")
        agent = LoggingProductAgent(tenant_id=TENANT_ID)
        
        # Test semantic search query
        response = await agent.chat_with_logging("Find me something colorful")
        print(f"\n✅ Semantic search response:\n{response}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_semantic_search())