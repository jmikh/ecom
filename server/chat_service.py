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
        
        # Extract response
        if result.get('final_answer'):
            try:
                validation_data = json.loads(result['final_answer'])
                response = self._format_product_response(validation_data)
            except json.JSONDecodeError:
                response = result['final_answer']
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
            
            # Extract response
            if result.get('final_answer'):
                try:
                    validation_data = json.loads(result['final_answer'])
                    
                    # Check if this is a ProductRecommendationResponse structure
                    # Must have both 'products' list and 'message' string, and products must be a list of dicts with expected fields
                    is_product_recommendation = (
                        isinstance(validation_data.get('products'), list) and
                        isinstance(validation_data.get('message'), str) and
                        len(validation_data.get('products', [])) > 0 and
                        all(
                            isinstance(p, dict) and 
                            'id' in p and 
                            'name' in p and 
                            'price_min' in p
                            for p in validation_data.get('products', [])
                        )
                    )
                    
                    if is_product_recommendation:
                        # Send structured data in a single chunk with type indicator
                        yield f"data: {json.dumps({'type': 'product_cards', 'data': validation_data, 'done': False})}\n\n"
                        yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                        
                        # Save message with structured product data
                        memory.add_message(
                            validation_data.get('message', 'Here are my recommendations'), 
                            "assistant",
                            structured_data=validation_data
                        )
                        return
                    else:
                        # Not a product recommendation, format as text
                        response = self._format_product_response(validation_data)
                        
                except json.JSONDecodeError:
                    response = result['final_answer']
            else:
                response = 'I apologize, but I was unable to generate a response.'
            
            # Save to memory
            memory.add_message(response, "assistant")
            
            # Stream response in chunks for text responses
            chunk_size = 50  # Characters per chunk
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                await asyncio.sleep(0.05)  # Small delay for streaming effect
            
            # Send completion signal
            yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
    
    def _format_product_response(self, response_data):
        """Format product recommendation response for web display"""
        # Check if this is the new ProductRecommendationResponse format
        if 'products' in response_data and 'message' in response_data:
            # Return the structured data as JSON for the frontend to render
            return json.dumps(response_data)
        
        # Legacy format fallback (can be removed later)
        lines = []
        for product in response_data.get('validated_products', []):
            status = "✅" if product['fits_criteria'] else "❌"
            lines.append(f"{status} **Product #{product['product_id']}**: {product['reason']}")
        
        if response_data.get('overall_summary'):
            lines.append(f"\n**Summary**: {response_data['overall_summary']}")
        
        return "\n\n".join(lines)
    
    def get_conversation_history(self, session_id: str, tenant_id: str) -> list:
        """Get conversation history for a session"""
        memory = ConversationMemory(session_id, tenant_id)
        return memory.get_messages(n=20)


# Global instance
web_chat_service = WebChatService()