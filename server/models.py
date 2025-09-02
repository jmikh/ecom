"""
Pydantic models for API requests and responses
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ChatMessage(BaseModel):
    content: str = Field(..., max_length=1000)
    role: str = Field(..., pattern="^(user|assistant)$")
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    tenant_id: str = Field(..., min_length=36, max_length=36)  # UUID format


class ChatResponse(BaseModel):
    session_id: str
    response: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionRequest(BaseModel):
    tenant_id: str = Field(..., min_length=36, max_length=36)
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    tenant_id: str
    created: bool
    expires_at: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)