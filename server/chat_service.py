"""
Chat service that integrates with the existing ChatServer
"""

import asyncio
import json
from typing import AsyncGenerator, Optional

from src.agent.main_graph import get_main_graph
from src.agent.graph_state import GraphState
from src.database.message_store import SessionManager, MessageStore, ConversationMemory
from src.database import get_database
from src.analytics.tracker import AnalyticsCallbackHandler
from src.shared.schemas import ChatServerResponse
from langchain_core.messages import HumanMessage


class WebChatService:
    """Adapter for the ChatServer to work with web requests"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.graph = get_main_graph()
        self.db = get_database()
    
    def get_or_create_session(self, session_id: Optional[str], tenant_id: str) -> str:
        """Get existing session or create new one"""
        if session_id:
            # Try to create/update the session
            session_data = self.session_manager.create_or_update_session(tenant_id, session_id)
            if session_data:
                return session_id
        
        # Create new session
        import uuid
        new_session_id = str(uuid.uuid4())
        self.session_manager.create_or_update_session(tenant_id, new_session_id)
        return new_session_id
    
    async def process_message(self, message: str, session_id: str, tenant_id: str) -> str:
        """Process a single message and return response"""
        memory = ConversationMemory(session_id, tenant_id)
        
        # Add user message to memory
        memory.add_message(message, "user")
        
        # Create GraphState - the graph will fetch context in classify_intent_node
        state = GraphState(
            chat_messages=[HumanMessage(content=message)],
            tenant_id=tenant_id,
            session_id=session_id
        )
        
        # Create analytics callback handler
        analytics_handler = AnalyticsCallbackHandler(tenant_id, session_id)
        
        # Run the graph with analytics tracking
        result = await self.graph.ainvoke(
            state.model_dump(),
            config={"callbacks": [analytics_handler]}
        )
        
        # Extract response from chat_server_response
        if result.get('chat_server_response'):
            chat_response = result['chat_server_response']
            
            # Build text representation
            text_parts = []
            if chat_response.first_message:
                text_parts.append(chat_response.first_message)
            if chat_response.products:
                text_parts.append(f"[Showing {len(chat_response.products)} products]")
            if chat_response.last_message:
                text_parts.append(chat_response.last_message)
            
            response = " ".join(text_parts) if text_parts else "Here are my recommendations"
        else:
            response = 'I apologize, but I was unable to generate a response. Please try again.'
        
        # Save to memory
        memory.add_message(response, "assistant")
        
        return response
    
    async def process_message_stream(
        self, 
        message: str, 
        session_id: str, 
        tenant_id: str
    ) -> AsyncGenerator[str, None]:
        """Process message and stream response chunks"""
        memory = ConversationMemory(session_id, tenant_id)
        
        # Add user message to memory
        memory.add_message(message, "user")
        
        # Create GraphState
        state = GraphState(
            chat_messages=[HumanMessage(content=message)],
            tenant_id=tenant_id,
            session_id=session_id
        )
        
        try:
            # Create analytics callback handler
            analytics_handler = AnalyticsCallbackHandler(tenant_id, session_id)
            
            # For now, we'll get the full response and chunk it
            # In future, we can implement true streaming from LangGraph
            result = await self.graph.ainvoke(
                state.model_dump(),
                config={"callbacks": [analytics_handler]}
            )
            
            # Extract response from chat_server_response
            if result.get('chat_server_response'):
                chat_response = result['chat_server_response']
                
                # Send as structured data to frontend
                yield f"data: {json.dumps({'type': 'chat_response', 'data': chat_response.model_dump(), 'done': False})}\n\n"
                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                
                # Save the entire response structure to memory
                # This preserves all product details for future reference
                memory.add_message(
                    json.dumps(chat_response.model_dump()),
                    "assistant",
                    structured_data=chat_response.model_dump()
                )
            else:
                # No structured response, send error message
                response = 'I apologize, but I was unable to generate a response.'
                
                # Save to memory
                memory.add_message(response, "assistant")
                
                # Stream error message in chunks
                chunk_size = 50
                for i in range(0, len(response), chunk_size):
                    chunk = response[i:i + chunk_size]
                    yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                    await asyncio.sleep(0.05)
                
                # Send completion signal
                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
    
    # Removed _format_product_response method - no longer needed
    
    def get_conversation_history(self, session_id: str, tenant_id: str) -> list:
        """Get conversation history for a session"""
        memory = ConversationMemory(session_id, tenant_id)
        return memory.get_messages(n=20)


# Global instance
web_chat_service = WebChatService()