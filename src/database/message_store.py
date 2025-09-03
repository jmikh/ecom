"""
PostgreSQL-based message storage
Replaces Redis for conversation history with persistent storage
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
import json

from src.database import get_database


class MessageStore:
    """PostgreSQL-based message storage for chat conversations"""
    
    def __init__(self):
        self.db = get_database()
    
    def get_conversation_context(
        self,
        tenant_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages for conversation context
        
        Args:
            tenant_id: Tenant UUID
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages in chronological order (oldest first)
        """
        query = """
            SELECT role, content, created_at, structured_data
            FROM chat_messages
            WHERE tenant_id = %s AND session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        # Fetch messages (they come in reverse chronological order)
        messages = self.db.run_read(
            query,
            (tenant_id, session_id, limit),
            tenant_id=tenant_id
        )
        
        # Reverse to get chronological order (oldest first)
        messages.reverse()
        
        # Format for LangChain compatibility
        # Include structured_data for assistant messages so LLM can see products shown
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["created_at"].isoformat() if msg["created_at"] else None,
                "structured_data": msg.get("structured_data")  # Include product data if present
            }
            for msg in messages
        ]
    
    def get_messages_for_session(
        self,
        tenant_id: str,
        session_id: str,
        include_system: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for a session
        
        Args:
            tenant_id: Tenant UUID
            session_id: Session identifier
            include_system: Whether to include system messages
            
        Returns:
            List of all messages in chronological order
        """
        role_filter = "" if include_system else "AND role != 'system'"
        
        query = f"""
            SELECT role, content, intent, model_used, cost, created_at
            FROM chat_messages
            WHERE tenant_id = %s AND session_id = %s {role_filter}
            ORDER BY created_at ASC
        """
        
        messages = self.db.run_read(
            query,
            (tenant_id, session_id),
            tenant_id=tenant_id
        )
        
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "intent": msg["intent"],
                "model_used": msg["model_used"],
                "cost": float(msg["cost"]) if msg["cost"] else None,
                "timestamp": msg["created_at"].isoformat() if msg["created_at"] else None
            }
            for msg in messages
        ]
    
    def clear_old_messages(self, days: int = 30) -> int:
        """
        Clear messages older than specified days
        
        Args:
            days: Number of days to keep messages
            
        Returns:
            Number of messages deleted
        """
        query = """
            DELETE FROM chat_messages
            WHERE created_at < NOW() - INTERVAL '%s days'
            RETURNING id
        """
        
        result = self.db.run_write(query, (days,))
        return len(result) if result else 0


class SessionManager:
    """Manage chat sessions in PostgreSQL"""
    
    def __init__(self):
        self.db = get_database()
    
    def create_or_update_session(
        self,
        tenant_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Create a new session or update existing one
        
        Args:
            tenant_id: Tenant UUID
            session_id: Session identifier
            
        Returns:
            Session information
        """
        query = """
            INSERT INTO chat_sessions (tenant_id, session_id, started_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (tenant_id, session_id) 
            DO UPDATE SET 
                message_count = chat_sessions.message_count + 1,
                ended_at = NOW()
            RETURNING id, session_id, started_at, message_count
        """
        
        result = self.db.run_write(
            query,
            (tenant_id, session_id),
            tenant_id=tenant_id
        )
        
        if result:
            return {
                "id": str(result[0]["id"]),
                "session_id": result[0]["session_id"],
                "started_at": result[0]["started_at"].isoformat(),
                "message_count": result[0]["message_count"]
            }
        return {"session_id": session_id}
    
    def update_session_metrics(
        self,
        tenant_id: str,
        session_id: str,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        llm_calls: int = 1,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None
    ):
        """
        Update session metrics after LLM call
        
        Args:
            tenant_id: Tenant UUID
            session_id: Session identifier
            tokens_used: Total tokens used in this call
            cost: Cost of this call
            llm_calls: Number of LLM calls (default 1)
            input_tokens: Input/prompt tokens used
            output_tokens: Output/completion tokens used
        """
        query = """
            UPDATE chat_sessions
            SET 
                llm_call_count = llm_call_count + %s,
                total_tokens_used = total_tokens_used + COALESCE(%s, 0),
                estimated_cost = estimated_cost + COALESCE(%s, 0),
                input_tokens = input_tokens + COALESCE(%s, 0),
                output_tokens = output_tokens + COALESCE(%s, 0),
                ended_at = NOW()
            WHERE tenant_id = %s AND session_id = %s
        """
        
        self.db.run_write(
            query,
            (llm_calls, tokens_used or 0, cost or 0, input_tokens or 0, output_tokens or 0, tenant_id, session_id),
            tenant_id=tenant_id
        )
    
    def get_active_sessions(self, tenant_id: str, minutes: int = 60) -> int:
        """
        Get count of active sessions in the last N minutes
        
        Args:
            tenant_id: Tenant UUID
            minutes: Time window in minutes
            
        Returns:
            Number of active sessions
        """
        query = """
            SELECT COUNT(DISTINCT session_id) as count
            FROM chat_sessions
            WHERE tenant_id = %s 
            AND (ended_at > NOW() - INTERVAL '%s minutes' OR ended_at IS NULL)
        """
        
        result = self.db.run_read(
            query,
            (tenant_id, minutes),
            tenant_id=tenant_id
        )
        
        return result[0]["count"] if result else 0


# Backward compatibility with existing code
class ConversationMemory:
    """
    Compatibility wrapper for existing Redis-based interface
    Redirects to PostgreSQL MessageStore
    """
    
    def __init__(self, session_id: str, tenant_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.store = MessageStore()
    
    def add_message(self, content: str, role: str, structured_data: Optional[Dict[str, Any]] = None, 
                   latency_ms: Optional[int] = None):
        """Add a message to conversation history - synchronous version"""
        # Since we're in an async context already, we'll use the synchronous database operations
        db = get_database()
        
        # Calculate latency for assistant messages if not provided
        if role == "assistant" and latency_ms is None:
            # Get the timestamp of the most recent user message
            query = """
                SELECT created_at 
                FROM chat_messages 
                WHERE tenant_id = %s AND session_id = %s AND role = 'user'
                ORDER BY created_at DESC
                LIMIT 1
            """
            result = db.run_read(
                query,
                (self.tenant_id, self.session_id),
                tenant_id=self.tenant_id
            )
            
            if result:
                user_msg_time = result[0]["created_at"]
                # Calculate latency in milliseconds
                from datetime import datetime
                now = datetime.now(user_msg_time.tzinfo)
                latency_ms = int((now - user_msg_time).total_seconds() * 1000)
        
        # Build the query to add a message
        query = """
            INSERT INTO chat_messages (
                tenant_id, session_id, role, content, structured_data, created_at, latency_ms
            ) VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
        
        # Convert structured_data to JSON if provided
        structured_json = json.dumps(structured_data) if structured_data else None
        
        try:
            db.run_write(
                query,
                (self.tenant_id, self.session_id, role, content, structured_json, latency_ms),
                tenant_id=self.tenant_id
            )
            
            # Also update session activity and latency metrics for assistant messages
            if role == "assistant" and latency_ms is not None:
                session_query = """
                    UPDATE chat_sessions 
                    SET 
                        ended_at = NOW(),
                        message_count = COALESCE(message_count, 0) + 1,
                        avg_latency_ms = (
                            CASE 
                                WHEN avg_latency_ms IS NULL THEN %s
                                ELSE (avg_latency_ms * (message_count - 1) + %s) / message_count
                            END
                        ),
                        max_latency_ms = GREATEST(COALESCE(max_latency_ms, %s), %s),
                        min_latency_ms = LEAST(COALESCE(min_latency_ms, %s), %s)
                    WHERE tenant_id = %s AND session_id = %s
                """
                db.run_write(
                    session_query,
                    (latency_ms, latency_ms, latency_ms, latency_ms, latency_ms, latency_ms, 
                     self.tenant_id, self.session_id),
                    tenant_id=self.tenant_id
                )
            else:
                session_query = """
                    UPDATE chat_sessions 
                    SET 
                        ended_at = NOW(),
                        message_count = COALESCE(message_count, 0) + 1
                    WHERE tenant_id = %s AND session_id = %s
                """
                db.run_write(
                    session_query,
                    (self.tenant_id, self.session_id),
                    tenant_id=self.tenant_id
                )
        except Exception as e:
            print(f"Error adding message: {e}")
    
    def get_messages(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        return self.store.get_conversation_context(
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            limit=n
        )