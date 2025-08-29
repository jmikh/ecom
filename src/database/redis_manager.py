"""
Redis Manager - Minimal session and conversation management
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis

from src.agent.config import config

# Global Redis client - initialized once and reused
try:
    redis_client = redis.from_url(config.get_redis_url())
    redis_client.ping()  # Test connection on import
    print(f"✅ Redis connection established: {config.get_redis_url()}")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    redis_client = None


class ConversationMemory:
    """Manages conversation history for a session"""
    
    def __init__(self, session_id: str, tenant_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.key = f"conversation:{tenant_id}:{session_id}"
    
    def add_message(self, content: str, role: str):
        """Add a message to conversation history"""
        if not redis_client:
            return
        
        message = {
            "content": content,
            "role": role,
            "timestamp": datetime.now().isoformat()
        }
        
        redis_client.rpush(self.key, json.dumps(message))
        redis_client.ltrim(self.key, -config.max_conversation_history, -1)
        redis_client.expire(self.key, config.session_ttl_seconds)
    
    def get_messages(self, n = 5) -> List[Dict[str, Any]]:
        """Get conversation history - returns last n messages in chronological order"""
        if not redis_client:
            return []
        
        # Get the last n messages (negative indexing gets from the end)
        messages = redis_client.lrange(self.key, -n, -1)
        return [json.loads(msg) for msg in messages]


class SessionManager:
    """Manages session data"""
    
    def create_or_fetch_session(self, session_id: str, tenant_id: str) -> Dict[str, Any]:
        """Create session if doesn't exist, or fetch existing session"""
        if not redis_client:
            return {"session_id": session_id, "tenant_id": tenant_id}
        
        key = f"session:{tenant_id}:{session_id}"
        data = redis_client.get(key)
        
        if data:
            # Update last active and return existing
            session_data = json.loads(data)
            session_data["last_active"] = datetime.now().isoformat()
            redis_client.setex(key, config.session_ttl_seconds, json.dumps(session_data))
            return session_data
        else:
            # Create new session
            session_data = {
                "session_id": session_id,
                "tenant_id": tenant_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            }
            redis_client.setex(key, config.session_ttl_seconds, json.dumps(session_data))
            return session_data