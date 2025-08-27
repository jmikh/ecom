"""
Memory and Session Management for Product Agent
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
    Manages user sessions and context
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
    
    def create_session(self, session_id: str, tenant_id: str, user_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new session"""
        session_data = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "user_preferences": {},
            "viewed_products": [],
            "search_history": [],
            "cart_items": [],
            "recommendations": [],
            **(user_data or {})
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
        """Update session data"""
        key = f"session:{tenant_id}:{session_id}"
        
        # Get existing data
        existing = self.get_session_data(session_id, tenant_id)
        if existing:
            # Merge updates
            existing.update(updates)
            existing["last_active"] = datetime.now().isoformat()
            
            # Save back
            self.redis_client.setex(
                key,
                config.session_ttl_seconds,
                json.dumps(existing)
            )
        else:
            # Create new session with updates
            self.create_session(session_id, tenant_id, updates)
    
    def add_viewed_product(self, session_id: str, tenant_id: str, product: Dict[str, Any]):
        """Add a product to viewed history"""
        session_data = self.get_session_data(session_id, tenant_id)
        
        if session_data:
            viewed = session_data.get("viewed_products", [])
            
            # Add product (avoid duplicates)
            product_id = product.get("id")
            if product_id and not any(p.get("id") == product_id for p in viewed):
                viewed.append({
                    "id": product_id,
                    "title": product.get("title"),
                    "price": product.get("min_price"),
                    "viewed_at": datetime.now().isoformat()
                })
                
                # Keep last 50 viewed products
                viewed = viewed[-50:]
                
                self.update_session(session_id, tenant_id, {"viewed_products": viewed})
    
    def get_user_preferences(self, session_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get user preferences from session"""
        session_data = self.get_session_data(session_id, tenant_id)
        
        if session_data:
            # Analyze viewed products and searches to infer preferences
            preferences = session_data.get("user_preferences", {})
            
            # Analyze viewed products
            viewed_products = session_data.get("viewed_products", [])
            if viewed_products:
                # Extract common patterns
                # This is a simplified version - could be much more sophisticated
                preferences["recently_viewed_count"] = len(viewed_products)
            
            # Analyze search history
            search_history = session_data.get("search_history", [])
            if search_history:
                preferences["recent_searches"] = [s.get("query") for s in search_history[-5:]]
            
            return preferences
        
        return {}
    
    def clear_session(self, session_id: str, tenant_id: str):
        """Clear session data"""
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
    
    def cleanup_expired_sessions(self, tenant_id: str):
        """Clean up expired sessions (this is handled by Redis TTL, but kept for manual cleanup)"""
        # Redis handles expiry automatically with TTL
        # This method is for any additional cleanup logic if needed
        pass


class ProductRecommendationCache:
    """
    Cache for product recommendations to improve performance
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(config.get_redis_url())
        self.cache_ttl = 3600  # 1 hour
    
    def get_recommendations(self, tenant_id: str, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached recommendations"""
        key = f"recommendations:{tenant_id}:{query_hash}"
        data = self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def cache_recommendations(self, tenant_id: str, query_hash: str, products: List[Dict[str, Any]]):
        """Cache product recommendations"""
        key = f"recommendations:{tenant_id}:{query_hash}"
        self.redis_client.setex(
            key,
            self.cache_ttl,
            json.dumps(products)
        )
    
    def invalidate_tenant_cache(self, tenant_id: str):
        """Invalidate all caches for a tenant (useful after data updates)"""
        pattern = f"recommendations:{tenant_id}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            self.redis_client.delete(*keys)