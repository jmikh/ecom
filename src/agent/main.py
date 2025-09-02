#!/usr/bin/env python3
"""
Simple chat server for terminal interaction
"""

import asyncio
import uuid
from typing import Optional
import json

from src.agent.main_graph import get_main_graph
from src.agent.graph_state import GraphState
from src.database.redis_manager import SessionManager, ConversationMemory
from src.database import get_database
from langchain_core.messages import HumanMessage


class ChatServer:
    def __init__(self):
        self.session_id: Optional[str] = None
        self.tenant_id: str = "6b028cbb-512d-4538-a3b1-71bc40f49ed1"  # Default tenant
        self.session_manager = SessionManager()
        self.memory: Optional[ConversationMemory] = None
        self.graph = get_main_graph()
        self.db = get_database()
        
    def create_session(self) -> str:
        self.session_id = str(uuid.uuid4())
        self.session_manager.create_or_fetch_session(self.session_id, self.tenant_id)
        self.memory = ConversationMemory(self.session_id, self.tenant_id)
        print(f"Session created: {self.session_id}")
        return self.session_id
    
    async def process_message(self, message: str) -> str:
        # Add user message to memory
        self.memory.add_message(message, "user")
        
        # Create GraphState - the graph will fetch context in classify_intent_node
        state = GraphState(
            chat_messages=[HumanMessage(content=message)],
            tenant_id=self.tenant_id,
            session_id=self.session_id
        )
        
        # Run the graph
        result = await self.graph.ainvoke(state.model_dump())
        
        # Extract response from final_answer
        if result.get('final_answer'):
            try:
                # Try to parse as JSON (from validation node)
                validation_data = json.loads(result['final_answer'])
                response = self._format_product_response(validation_data)
            except json.JSONDecodeError:
                response = result['final_answer']
        else:
            response = 'No response generated'
        
        # Save to memory
        self.memory.add_message(response, "assistant")
        
        return response
    
    def _format_product_response(self, validation_data):
        """Format product validation response for terminal display"""
        lines = []
        for product in validation_data.get('validated_products', []):
            status = "✅" if product['fits_criteria'] else "❌"
            lines.append(f"{status} Product #{product['product_id']}: {product['reason']}")
        
        if validation_data.get('overall_summary'):
            lines.append(f"\nSummary: {validation_data['overall_summary']}")
        
        return "\n".join(lines)
    
    async def chat_loop(self):
        print("Chat started. Type 'quit' to exit.")
        
        while True:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() == 'quit':
                break
            
            if not user_input:
                continue
            
            response = await self.process_message(user_input)
            print(f"Assistant: {response}")


async def main():
    server = ChatServer()
    server.create_session()
    await server.chat_loop()
    server.db.close()


if __name__ == "__main__":
    asyncio.run(main())