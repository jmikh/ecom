"""
Server-specific configuration
"""

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class ServerConfig:
    # API Server Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    ALLOW_CREDENTIALS: bool = True
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "1000"))
    
    # Widget Settings
    CDN_URL: str = os.getenv("CDN_URL", "http://localhost:8000/static")
    WIDGET_VERSION: str = os.getenv("WIDGET_VERSION", "1.0.0")
    
    # Tenant API Keys (in production, store in database)
    # Format: {tenant_id: api_key}
    TENANT_API_KEYS = {
        "6b028cbb-512d-4538-a3b1-71bc40f49ed1": "test-api-key-123"
    }


server_config = ServerConfig()