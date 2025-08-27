#!/usr/bin/env python3
"""
Run the Product Agent with LangSmith Tracing
Uses the actual LangGraph agent with proper LangSmith debugging instead of custom logging
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.agent import ProductAgent

async def main():
    """Run the agent with LangSmith tracing"""
    
    # Replace with your actual tenant ID
    TENANT_ID = "75a3f9b9-effc-4e9f-a829-5cdda2ec729d"
    
    print("""
╔══════════════════════════════════════════════╗
║         LangGraph Product Agent              ║
║       🔍 With LangSmith Tracing             ║
╚══════════════════════════════════════════════╝
    """)
    
    try:
        # Create the actual LangGraph agent (not the logging wrapper)
        agent = ProductAgent(tenant_id=TENANT_ID)
        
        print(f"🎯 Agent ready! Session ID: {agent.session_id}")
        print("🔍 LangSmith tracing enabled - check https://smith.langchain.com")
        print("💬 Type 'quit' to exit\n")
        
        # Test queries to demonstrate different capabilities
        if len(sys.argv) > 1 and sys.argv[1] == "--demo":
            demo_queries = [
                "Show me jewelry under $50",
                # "What outdoor gear do you have under $100?", 
                # "Find me something colorful",
                # "Tell me more about the camp stool"
            ]
            
            for i, query in enumerate(demo_queries, 1):
                print(f"\n{'='*60}")
                print(f"🧪 DEMO QUERY {i}: {query}")
                print(f"{'='*60}")
                
                response = await agent.chat(query)
                print(f"\n🤖 RESPONSE:\n{response}")
                
                # Wait between queries
                await asyncio.sleep(2)
                
        else:
            # Interactive mode
            while True:
                try:
                    query = input("\n🗣️  You: ").strip()
                    
                    if query.lower() in ['quit', 'exit', 'q']:
                        break
                    
                    if not query:
                        continue
                    
                    print(f"\n🤖 Processing: '{query}'")
                    response = await agent.chat(query)
                    
                    print(f"\n💬 Agent: {response}")
                    
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
        
        print(f"\n🔍 Check LangSmith dashboard: https://smith.langchain.com")
        print("   - View all LLM calls and tool executions")
        print("   - Analyze agent decision making") 
        print("   - Debug performance and errors")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())