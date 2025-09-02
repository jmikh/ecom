"""
Pydantic schemas for dashboard
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class TenantSettings(BaseModel):
    """Tenant configuration settings"""
    description: Optional[str] = Field(None, description="Store description")
    brand_voice: Optional[str] = Field(None, description="Brand voice for AI responses")
    store_url: Optional[str] = Field(None, description="Store website URL")
    logo_url: Optional[str] = Field(None, description="Store logo URL")
    ai_temperature: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="AI response temperature")
    max_products_shown: Optional[int] = Field(5, ge=1, le=20, description="Maximum products to show")
    
    class Config:
        schema_extra = {
            "example": {
                "description": "Premium outdoor gear and camping equipment",
                "brand_voice": "Friendly, knowledgeable, and enthusiastic about outdoor adventures",
                "store_url": "https://example-store.com",
                "logo_url": "https://example-store.com/logo.png",
                "ai_temperature": 0.7,
                "max_products_shown": 5
            }
        }


class DashboardMetrics(BaseModel):
    """Main dashboard overview metrics"""
    total_sessions: int = Field(description="Total chat sessions all time")
    messages_today: int = Field(description="Messages sent today")
    cost_today: float = Field(description="LLM costs today in USD")
    active_sessions: int = Field(description="Active sessions in last hour")
    days_active: Optional[int] = Field(None, description="Number of days with activity")
    
    class Config:
        schema_extra = {
            "example": {
                "total_sessions": 1234,
                "messages_today": 56,
                "cost_today": 2.45,
                "active_sessions": 3,
                "days_active": 30
            }
        }


class SessionAnalytics(BaseModel):
    """Session analytics over time"""
    date: str = Field(description="Date in ISO format")
    session_count: int = Field(description="Number of sessions")
    unique_sessions: int = Field(description="Number of unique sessions")
    total_messages: int = Field(description="Total messages")
    daily_cost: float = Field(description="Cost for the day")


class MessageVolume(BaseModel):
    """Message volume statistics"""
    date: str = Field(description="Date in ISO format")
    user_messages: int = Field(description="Messages from users")
    assistant_messages: int = Field(description="Messages from assistant")
    total_messages: int = Field(description="Total messages")


class CostBreakdown(BaseModel):
    """Cost breakdown by model"""
    models: List[Dict[str, Any]] = Field(description="List of models with costs")
    total_cost: float = Field(description="Total cost for period")
    period_days: int = Field(description="Number of days in period")


class ProductEvent(BaseModel):
    """Product analytics event"""
    id: int = Field(description="Product ID")
    name: str = Field(description="Product name")
    vendor: Optional[str] = Field(None, description="Product vendor")
    price_min: float = Field(description="Minimum price")
    price_max: float = Field(description="Maximum price")
    event_count: int = Field(description="Number of events")


class IntentDistribution(BaseModel):
    """Distribution of user intents"""
    intent: str = Field(description="Intent type")
    count: int = Field(description="Number of occurrences")


class HourlyActivity(BaseModel):
    """Activity pattern by hour"""
    hour: int = Field(ge=0, le=23, description="Hour of day (0-23)")
    message_count: int = Field(description="Number of messages")


class TenantInfo(BaseModel):
    """Complete tenant information"""
    tenant_id: str = Field(description="Tenant UUID")
    name: str = Field(description="Tenant name")
    description: Optional[str] = Field(None, description="Store description")
    brand_voice: Optional[str] = Field(None, description="Brand voice")
    store_url: Optional[str] = Field(None, description="Store URL")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Additional settings")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")