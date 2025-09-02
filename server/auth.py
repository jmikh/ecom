"""
Authentication and authorization middleware
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import hmac

from server.config import server_config
from src.database import get_database


class TenantAuth:
    """Handles tenant authentication via API keys"""
    
    @staticmethod
    def verify_tenant(tenant_id: str, api_key: Optional[str] = None) -> bool:
        """Verify tenant exists and API key matches if provided"""
        # In production, check against database
        if tenant_id not in server_config.TENANT_API_KEYS:
            return False
        
        if api_key:
            expected_key = server_config.TENANT_API_KEYS.get(tenant_id)
            return hmac.compare_digest(api_key, expected_key)
        
        # For now, allow access if tenant exists (for widget embedding)
        return True
    
    @staticmethod
    def verify_tenant_in_db(tenant_id: str) -> Dict[str, Any]:
        """Verify tenant exists in database"""
        db = get_database()
        try:
            result = db.run_read(
                "SELECT tenant_id, name FROM tenants WHERE tenant_id = %s",
                (tenant_id,)
            )
            if not result:
                raise HTTPException(status_code=404, detail="Tenant not found")
            return result[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
    
    def check_rate_limit(self, key: str, limit: int = 20, window: int = 60) -> bool:
        """Check if request is within rate limit"""
        now = datetime.now()
        window_start = now - timedelta(seconds=window)
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Clean old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if req_time > window_start
        ]
        
        # Check limit
        if len(self.requests[key]) >= limit:
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter()


async def verify_rate_limit(request: Request):
    """Dependency to check rate limits"""
    client_ip = request.client.host
    
    if not rate_limiter.check_rate_limit(
        client_ip, 
        server_config.RATE_LIMIT_PER_MINUTE
    ):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. Please try again later."
        )