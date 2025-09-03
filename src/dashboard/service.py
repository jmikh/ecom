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
                input_tokens,
                output_tokens,
                estimated_cost,
                avg_latency_ms,
                max_latency_ms,
                min_latency_ms
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
                "input_tokens": row["input_tokens"] or 0,
                "output_tokens": row["output_tokens"] or 0,
                "estimated_cost": float(row["estimated_cost"]) if row["estimated_cost"] else 0.0,
                "avg_latency_ms": row.get("avg_latency_ms"),
                "max_latency_ms": row.get("max_latency_ms"),
                "min_latency_ms": row.get("min_latency_ms")
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
                created_at,
                latency_ms
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
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None,
                "latency_ms": msg["latency_ms"]
            }
            for msg in messages
        ]
    
    def get_latency_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get latency metrics for assistant messages
        
        Returns:
            Dictionary with average latency, worst latency per thread, and percentiles
        """
        # Get average latency across all assistant messages
        avg_query = """
            SELECT 
                AVG(latency_ms) as avg_latency,
                MIN(latency_ms) as min_latency,
                MAX(latency_ms) as max_latency,
                COUNT(*) as message_count
            FROM chat_messages
            WHERE tenant_id = %s 
                AND role = 'assistant' 
                AND latency_ms IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
        """
        
        avg_result = self.db.run_read(avg_query, (self.tenant_id, days))
        
        # Get worst latency per thread/session
        worst_per_thread_query = """
            SELECT 
                session_id,
                MAX(latency_ms) as max_latency,
                AVG(latency_ms) as avg_latency,
                COUNT(*) as message_count
            FROM chat_messages
            WHERE tenant_id = %s 
                AND role = 'assistant' 
                AND latency_ms IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY session_id
            ORDER BY max_latency DESC
            LIMIT 10
        """
        
        worst_threads = self.db.run_read(worst_per_thread_query, (self.tenant_id, days))
        
        # Get latency percentiles
        percentiles_query = """
            SELECT 
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) as p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY latency_ms) as p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) as p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99
            FROM chat_messages
            WHERE tenant_id = %s 
                AND role = 'assistant' 
                AND latency_ms IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
        """
        
        percentiles = self.db.run_read(percentiles_query, (self.tenant_id, days))
        
        # Get latency over time for graph
        time_series_query = """
            SELECT 
                DATE_TRUNC('hour', created_at) as hour,
                AVG(latency_ms) as avg_latency,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) as p50,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) as p90,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99,
                COUNT(*) as message_count
            FROM chat_messages
            WHERE tenant_id = %s 
                AND role = 'assistant' 
                AND latency_ms IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY hour
            ORDER BY hour ASC
        """
        
        time_series = self.db.run_read(time_series_query, (self.tenant_id, days))
        
        return {
            "summary": {
                "avg_latency_ms": float(avg_result[0]["avg_latency"]) if avg_result and avg_result[0]["avg_latency"] else 0,
                "min_latency_ms": avg_result[0]["min_latency"] if avg_result else 0,
                "max_latency_ms": avg_result[0]["max_latency"] if avg_result else 0,
                "message_count": avg_result[0]["message_count"] if avg_result else 0
            },
            "worst_threads": [
                {
                    "session_id": thread["session_id"],
                    "max_latency_ms": thread["max_latency"],
                    "avg_latency_ms": float(thread["avg_latency"]) if thread["avg_latency"] else 0,
                    "message_count": thread["message_count"]
                }
                for thread in worst_threads
            ],
            "percentiles": {
                "p50": float(percentiles[0]["p50"]) if percentiles and percentiles[0]["p50"] else 0,
                "p75": float(percentiles[0]["p75"]) if percentiles and percentiles[0]["p75"] else 0,
                "p90": float(percentiles[0]["p90"]) if percentiles and percentiles[0]["p90"] else 0,
                "p95": float(percentiles[0]["p95"]) if percentiles and percentiles[0]["p95"] else 0,
                "p99": float(percentiles[0]["p99"]) if percentiles and percentiles[0]["p99"] else 0
            },
            "time_series": [
                {
                    "hour": row["hour"].isoformat() if row["hour"] else None,
                    "avg_latency_ms": float(row["avg_latency"]) if row["avg_latency"] else 0,
                    "p50": float(row["p50"]) if row["p50"] else 0,
                    "p90": float(row["p90"]) if row["p90"] else 0,
                    "p99": float(row["p99"]) if row["p99"] else 0,
                    "message_count": row["message_count"]
                }
                for row in time_series
            ]
        }