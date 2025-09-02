"""
Data aggregation for dashboard metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from src.database import get_database


class DashboardAggregator:
    """
    Aggregate analytics data for dashboard display
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize aggregator for a specific tenant
        
        Args:
            tenant_id: Tenant UUID
        """
        self.tenant_id = tenant_id
        self.db = get_database()
    
    def get_overview_metrics(self) -> Dict[str, Any]:
        """
        Get high-level overview metrics for dashboard
        
        Returns:
            Dictionary with overview metrics
        """
        metrics = {}
        
        # Total sessions (all time)
        query = """
            SELECT COUNT(*) as total_sessions,
                   COUNT(DISTINCT DATE(started_at)) as days_active
            FROM chat_sessions
            WHERE tenant_id = %s
        """
        result = self.db.run_read(query, (self.tenant_id,), tenant_id=self.tenant_id)
        if result:
            metrics["total_sessions"] = result[0]["total_sessions"]
            metrics["days_active"] = result[0]["days_active"]
        
        # Messages today
        query = """
            SELECT COUNT(*) as messages_today
            FROM chat_messages
            WHERE tenant_id = %s
            AND DATE(created_at) = CURRENT_DATE
        """
        result = self.db.run_read(query, (self.tenant_id,), tenant_id=self.tenant_id)
        if result:
            metrics["messages_today"] = result[0]["messages_today"]
        
        # Cost today
        query = """
            SELECT COALESCE(SUM(estimated_cost), 0) as cost_today
            FROM chat_sessions
            WHERE tenant_id = %s
            AND DATE(started_at) = CURRENT_DATE
        """
        result = self.db.run_read(query, (self.tenant_id,), tenant_id=self.tenant_id)
        if result:
            metrics["cost_today"] = float(result[0]["cost_today"])
        
        # Active sessions (last hour)
        query = """
            SELECT COUNT(DISTINCT session_id) as active_sessions
            FROM chat_messages
            WHERE tenant_id = %s
            AND created_at > NOW() - INTERVAL '1 hour'
        """
        result = self.db.run_read(query, (self.tenant_id,), tenant_id=self.tenant_id)
        if result:
            metrics["active_sessions"] = result[0]["active_sessions"]
        
        return metrics
    
    def get_sessions_over_time(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get session counts over time
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily session counts
        """
        query = """
            SELECT 
                DATE(started_at) as date,
                COUNT(*) as session_count,
                COUNT(DISTINCT session_id) as unique_sessions,
                SUM(message_count) as total_messages,
                COALESCE(SUM(estimated_cost), 0) as daily_cost
            FROM chat_sessions
            WHERE tenant_id = %s
            AND started_at > NOW() - INTERVAL '%s days'
            GROUP BY DATE(started_at)
            ORDER BY date ASC
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, days),
            tenant_id=self.tenant_id
        )
        
        if not results:
            return []
        
        # Fill in missing days with zeros
        data_by_date = {
            row["date"]: {
                "date": row["date"].isoformat(),
                "session_count": row["session_count"],
                "unique_sessions": row["unique_sessions"],
                "total_messages": row["total_messages"] or 0,
                "daily_cost": float(row["daily_cost"])
            }
            for row in results
        }
        
        # Generate complete date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        complete_data = []
        current_date = start_date
        while current_date <= end_date:
            if current_date in data_by_date:
                complete_data.append(data_by_date[current_date])
            else:
                complete_data.append({
                    "date": current_date.isoformat(),
                    "session_count": 0,
                    "unique_sessions": 0,
                    "total_messages": 0,
                    "daily_cost": 0.0
                })
            current_date += timedelta(days=1)
        
        return complete_data
    
    def get_message_volume(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get message volume statistics
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily message statistics
        """
        query = """
            SELECT 
                DATE(created_at) as date,
                role,
                COUNT(*) as count
            FROM chat_messages
            WHERE tenant_id = %s
            AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY DATE(created_at), role
            ORDER BY date ASC, role
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, days),
            tenant_id=self.tenant_id
        )
        
        if not results:
            return []
        
        # Group by date
        volume_by_date = {}
        for row in results:
            date_str = row["date"].isoformat()
            if date_str not in volume_by_date:
                volume_by_date[date_str] = {
                    "date": date_str,
                    "user_messages": 0,
                    "assistant_messages": 0,
                    "total_messages": 0
                }
            
            if row["role"] == "user":
                volume_by_date[date_str]["user_messages"] = row["count"]
            elif row["role"] == "assistant":
                volume_by_date[date_str]["assistant_messages"] = row["count"]
            
            volume_by_date[date_str]["total_messages"] += row["count"]
        
        return list(volume_by_date.values())
    
    def get_cost_breakdown(self, days: int = 7) -> Dict[str, Any]:
        """
        Get cost breakdown by model
        
        Args:
            days: Number of days to look back
            
        Returns:
            Cost breakdown statistics
        """
        query = """
            SELECT 
                model_used,
                COUNT(*) as call_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(cost) as total_cost
            FROM chat_messages
            WHERE tenant_id = %s
            AND model_used IS NOT NULL
            AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY model_used
            ORDER BY total_cost DESC
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, days),
            tenant_id=self.tenant_id
        )
        
        if not results:
            return {"models": [], "total_cost": 0.0}
        
        models = []
        total_cost = 0.0
        
        for row in results:
            model_cost = float(row["total_cost"]) if row["total_cost"] else 0.0
            total_cost += model_cost
            
            models.append({
                "model": row["model_used"],
                "call_count": row["call_count"],
                "prompt_tokens": row["total_prompt_tokens"] or 0,
                "completion_tokens": row["total_completion_tokens"] or 0,
                "cost": model_cost
            })
        
        return {
            "models": models,
            "total_cost": total_cost,
            "period_days": days
        }
    
    def get_intent_distribution(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get distribution of user intents
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of intent counts
        """
        query = """
            SELECT 
                intent,
                COUNT(*) as count
            FROM chat_messages
            WHERE tenant_id = %s
            AND role = 'user'
            AND intent IS NOT NULL
            AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY intent
            ORDER BY count DESC
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, days),
            tenant_id=self.tenant_id
        )
        
        return [
            {
                "intent": row["intent"],
                "count": row["count"]
            }
            for row in results
        ] if results else []
    
    def get_hourly_activity(self) -> List[Dict[str, Any]]:
        """
        Get activity pattern by hour of day (last 7 days)
        
        Returns:
            List of hourly activity counts
        """
        query = """
            SELECT 
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as message_count
            FROM chat_messages
            WHERE tenant_id = %s
            AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
        """
        
        results = self.db.run_read(query, (self.tenant_id,), tenant_id=self.tenant_id)
        
        # Fill in all 24 hours
        hourly_data = {int(row["hour"]): row["message_count"] for row in results} if results else {}
        
        return [
            {
                "hour": hour,
                "message_count": hourly_data.get(hour, 0)
            }
            for hour in range(24)
        ]