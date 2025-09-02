"""
Dashboard business logic service
"""

from typing import Dict, Any, List, Optional
import json
from datetime import datetime

from src.database import get_database
from src.analytics.aggregator import DashboardAggregator
from src.analytics.tracker import ProductAnalyticsTracker
from .schemas import TenantSettings, TenantInfo


class DashboardService:
    """
    Service layer for dashboard operations
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize dashboard service for a tenant
        
        Args:
            tenant_id: Tenant UUID
        """
        self.tenant_id = tenant_id
        self.db = get_database()
        self.aggregator = DashboardAggregator(tenant_id)
        self.product_tracker = ProductAnalyticsTracker(tenant_id)
    
    def get_tenant_info(self) -> Optional[TenantInfo]:
        """
        Get complete tenant information
        
        Returns:
            Tenant information or None if not found
        """
        query = """
            SELECT 
                tenant_id, name, description, brand_voice,
                store_url, logo_url, settings,
                created_at, updated_at
            FROM tenants
            WHERE tenant_id = %s
        """
        
        result = self.db.run_read(
            query,
            (self.tenant_id,),
            tenant_id=self.tenant_id
        )
        
        if not result:
            return None
        
        row = result[0]
        return TenantInfo(
            tenant_id=str(row["tenant_id"]),
            name=row["name"],
            description=row["description"],
            brand_voice=row["brand_voice"],
            store_url=row["store_url"],
            logo_url=row["logo_url"],
            settings=row["settings"] or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    
    def update_tenant_settings(self, settings: TenantSettings) -> bool:
        """
        Update tenant settings
        
        Args:
            settings: New settings to apply
            
        Returns:
            True if successful
        """
        # Build dynamic update query based on provided fields
        update_fields = []
        params = []
        
        if settings.description is not None:
            update_fields.append("description = %s")
            params.append(settings.description)
        
        if settings.brand_voice is not None:
            update_fields.append("brand_voice = %s")
            params.append(settings.brand_voice)
        
        if settings.store_url is not None:
            update_fields.append("store_url = %s")
            params.append(settings.store_url)
        
        if settings.logo_url is not None:
            update_fields.append("logo_url = %s")
            params.append(settings.logo_url)
        
        # Update JSON settings
        json_settings = {}
        if settings.ai_temperature is not None:
            json_settings["ai_temperature"] = settings.ai_temperature
        if settings.max_products_shown is not None:
            json_settings["max_products_shown"] = settings.max_products_shown
        
        if json_settings:
            update_fields.append("settings = settings || %s::jsonb")
            params.append(json.dumps(json_settings))
        
        # Always update the updated_at timestamp
        update_fields.append("updated_at = NOW()")
        
        if not update_fields:
            return True  # Nothing to update
        
        # Add tenant_id to params
        params.append(self.tenant_id)
        
        query = f"""
            UPDATE tenants
            SET {', '.join(update_fields)}
            WHERE tenant_id = %s
        """
        
        try:
            self.db.run_write(query, tuple(params), tenant_id=self.tenant_id)
            return True
        except Exception as e:
            print(f"❌ Error updating tenant settings: {e}")
            return False
    
    def get_overview_metrics(self) -> Dict[str, Any]:
        """Get dashboard overview metrics"""
        return self.aggregator.get_overview_metrics()
    
    def get_sessions_over_time(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get session analytics over time"""
        return self.aggregator.get_sessions_over_time(days)
    
    def get_message_volume(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get message volume statistics"""
        return self.aggregator.get_message_volume(days)
    
    def get_cost_breakdown(self, days: int = 7) -> Dict[str, Any]:
        """Get cost breakdown by model"""
        return self.aggregator.get_cost_breakdown(days)
    
    def get_top_products(
        self,
        event_type: str = "recommended",
        limit: int = 10,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get top products by event type"""
        return self.product_tracker.get_top_products(event_type, limit, days)
    
    def get_intent_distribution(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get distribution of user intents"""
        return self.aggregator.get_intent_distribution(days)
    
    def get_hourly_activity(self) -> List[Dict[str, Any]]:
        """Get hourly activity pattern"""
        return self.aggregator.get_hourly_activity()
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent chat sessions
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of recent sessions with details
        """
        query = """
            SELECT 
                session_id,
                started_at,
                ended_at,
                message_count,
                llm_call_count,
                total_tokens_used,
                estimated_cost
            FROM chat_sessions
            WHERE tenant_id = %s
            ORDER BY started_at DESC
            LIMIT %s
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, limit),
            tenant_id=self.tenant_id
        )
        
        if not results:
            return []
        
        return [
            {
                "session_id": row["session_id"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "ended_at": row["ended_at"].isoformat() if row["ended_at"] else None,
                "duration_minutes": (
                    (row["ended_at"] - row["started_at"]).total_seconds() / 60
                    if row["ended_at"] and row["started_at"]
                    else None
                ),
                "message_count": row["message_count"],
                "llm_call_count": row["llm_call_count"],
                "total_tokens_used": row["total_tokens_used"],
                "estimated_cost": float(row["estimated_cost"]) if row["estimated_cost"] else 0.0
            }
            for row in results
        ]
    
    def export_analytics_csv(self, days: int = 30) -> str:
        """
        Export analytics data as CSV
        
        Args:
            days: Number of days to export
            
        Returns:
            CSV string
        """
        import csv
        import io
        
        # Get session data
        sessions = self.get_sessions_over_time(days)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["date", "session_count", "unique_sessions", "total_messages", "daily_cost"]
        )
        
        writer.writeheader()
        writer.writerows(sessions)
        
        return output.getvalue()
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a specific session"""
        query = """
            SELECT 
                role,
                content,
                structured_data,
                model_used,
                cost,
                created_at
            FROM chat_messages
            WHERE tenant_id = %s AND session_id = %s
            ORDER BY created_at ASC
        """
        
        messages = self.db.run_read(query, (self.tenant_id, session_id))
        
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "structured_data": msg["structured_data"],  # This will be JSONB from PostgreSQL
                "model_used": msg["model_used"],
                "cost": float(msg["cost"]) if msg["cost"] else 0,
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None
            }
            for msg in messages
        ]