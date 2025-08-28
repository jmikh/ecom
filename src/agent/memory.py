"""
Memory Management for Product Agent - Conversation History Only
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis

from .config import config


class ConversationMemory:
    """
    Manages conversation history for a session
    """
    
    def __init__(self, session_id: str, tenant_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.redis_client = redis.from_url(config.get_redis_url())
        self.key = f"conversation:{tenant_id}:{session_id}"
        
        # Test connection and fail fast if Redis is not available
        try:
            self.redis_client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis at {config.get_redis_url()}: {e}")
        except Exception as e:
            raise ConnectionError(f"Redis connection error: {e}")
        
    def add_message(self, content: str, role: str):
        """Add a message to conversation history"""
        message = {
            "content": content,
            "role": role,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to Redis list
        self.redis_client.rpush(self.key, json.dumps(message))
        
        # Trim to max history length
        self.redis_client.ltrim(self.key, -config.max_conversation_history, -1)
        
        # Set TTL
        self.redis_client.expire(self.key, config.session_ttl_seconds)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get full conversation history"""
        messages = self.redis_client.lrange(self.key, 0, -1)
        return [json.loads(msg) for msg in messages]
    
    def get_recent_messages(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get n most recent messages"""
        messages = self.redis_client.lrange(self.key, -n, -1)
        return [json.loads(msg) for msg in messages]
    
    def clear(self):
        """Clear conversation history"""
        self.redis_client.delete(self.key)
    
    def get_summary(self) -> Optional[str]:
        """Get conversation summary (for long conversations)"""
        summary_key = f"{self.key}:summary"
        summary = self.redis_client.get(summary_key)
        return summary.decode() if summary else None
    
    def save_summary(self, summary: str):
        """Save conversation summary"""
        summary_key = f"{self.key}:summary"
        self.redis_client.setex(
            summary_key, 
            config.session_ttl_seconds, 
            summary
        )


class SessionManager:
    """
    Manages basic session data for conversation continuity
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(config.get_redis_url())
        
        # Test connection and fail fast if Redis is not available
        try:
            self.redis_client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis at {config.get_redis_url()}: {e}")
        except Exception as e:
            raise ConnectionError(f"Redis connection error: {e}")
    
    def create_session(self, session_id: str, tenant_id: str) -> Dict[str, Any]:
        """Create a new session with minimal data"""
        session_data = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        
        key = f"session:{tenant_id}:{session_id}"
        self.redis_client.setex(
            key,
            config.session_ttl_seconds,
            json.dumps(session_data)
        )
        
        return session_data
    
    def get_session_data(self, session_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        key = f"session:{tenant_id}:{session_id}"
        data = self.redis_client.get(key)
        
        if data:
            # Update last active and extend TTL
            session_data = json.loads(data)
            session_data["last_active"] = datetime.now().isoformat()
            self.redis_client.setex(
                key,
                config.session_ttl_seconds,
                json.dumps(session_data)
            )
            return session_data
        
        return None
    
    def update_session(self, session_id: str, tenant_id: str, updates: Dict[str, Any]):
        """Update session data (mainly for last_active timestamp)"""
        key = f"session:{tenant_id}:{session_id}"
        
        # Get existing data
        existing = self.get_session_data(session_id, tenant_id)
        if existing:
            # Only update last_active and any minimal session data
            existing["last_active"] = datetime.now().isoformat()
            
            # Save back
            self.redis_client.setex(
                key,
                config.session_ttl_seconds,
                json.dumps(existing)
            )
        else:
            # Create new session
            self.create_session(session_id, tenant_id)
    
    def clear_session(self, session_id: str, tenant_id: str):
        """Clear session data and conversation history"""
        key = f"session:{tenant_id}:{session_id}"
        conversation_key = f"conversation:{tenant_id}:{session_id}"
        
        self.redis_client.delete(key)
        self.redis_client.delete(conversation_key)
    
    def get_active_sessions(self, tenant_id: str) -> List[str]:
        """Get list of active sessions for a tenant"""
        pattern = f"session:{tenant_id}:*"
        keys = self.redis_client.keys(pattern)
        
        active_sessions = []
        for key in keys:
            session_id = key.decode().split(":")[-1]
            active_sessions.append(session_id)
        
        return active_sessions