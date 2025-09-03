"""
Dashboard API routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any

from src.dashboard.service import DashboardService
from src.dashboard.schemas import (
    TenantSettings,
    DashboardMetrics,
    TenantInfo,
    SessionAnalytics,
    MessageVolume,
    CostBreakdown,
    ProductEvent,
    IntentDistribution,
    HourlyActivity
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/{tenant_id}/info", response_model=TenantInfo)
async def get_tenant_info(tenant_id: str):
    """
    Get complete tenant information including settings
    """
    service = DashboardService(tenant_id)
    info = service.get_tenant_info()
    
    if not info:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return info


@router.put("/{tenant_id}/settings")
async def update_tenant_settings(tenant_id: str, settings: TenantSettings):
    """
    Update tenant settings (description, brand voice, etc.)
    """
    service = DashboardService(tenant_id)
    success = service.update_tenant_settings(settings)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    
    return {"status": "success", "message": "Settings updated"}


@router.get("/{tenant_id}/overview", response_model=Dict[str, Any])
async def get_overview_metrics(tenant_id: str):
    """
    Get dashboard overview metrics
    """
    service = DashboardService(tenant_id)
    metrics = service.get_overview_metrics()
    return metrics


@router.get("/{tenant_id}/sessions", response_model=List[Dict[str, Any]])
async def get_sessions_over_time(
    tenant_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back")
):
    """
    Get session analytics over time
    """
    service = DashboardService(tenant_id)
    sessions = service.get_sessions_over_time(days)
    return sessions


@router.get("/{tenant_id}/messages", response_model=List[Dict[str, Any]])
async def get_message_volume(
    tenant_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back")
):
    """
    Get message volume statistics
    """
    service = DashboardService(tenant_id)
    volume = service.get_message_volume(days)
    return volume


@router.get("/{tenant_id}/costs", response_model=Dict[str, Any])
async def get_cost_breakdown(
    tenant_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back")
):
    """
    Get cost breakdown by model
    """
    service = DashboardService(tenant_id)
    costs = service.get_cost_breakdown(days)
    return costs


@router.get("/{tenant_id}/latency", response_model=Dict[str, Any])
async def get_latency_metrics(
    tenant_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back")
):
    """
    Get latency metrics for assistant messages including:
    - Average latency across all messages
    - Worst latency per thread
    - Latency percentiles (P50, P75, P90, P95, P99)
    - Time series data for latency graphs
    """
    service = DashboardService(tenant_id)
    metrics = service.get_latency_metrics(days)
    return metrics


@router.get("/{tenant_id}/products/top", response_model=List[Dict[str, Any]])
async def get_top_products(
    tenant_id: str,
    event_type: str = Query("recommended", enum=["recommended", "inquired", "clicked"]),
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=90)
):
    """
    Get top products by event type
    """
    service = DashboardService(tenant_id)
    products = service.get_top_products(event_type, limit, days)
    return products


@router.get("/{tenant_id}/intents", response_model=List[Dict[str, Any]])
async def get_intent_distribution(
    tenant_id: str,
    days: int = Query(7, ge=1, le=90)
):
    """
    Get distribution of user intents
    """
    service = DashboardService(tenant_id)
    intents = service.get_intent_distribution(days)
    return intents


@router.get("/{tenant_id}/activity/hourly", response_model=List[Dict[str, Any]])
async def get_hourly_activity(tenant_id: str):
    """
    Get hourly activity pattern
    """
    service = DashboardService(tenant_id)
    activity = service.get_hourly_activity()
    return activity


@router.get("/{tenant_id}/sessions/recent", response_model=List[Dict[str, Any]])
async def get_recent_sessions(
    tenant_id: str,
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get recent chat sessions with details
    """
    service = DashboardService(tenant_id)
    sessions = service.get_recent_sessions(limit)
    return sessions


@router.get("/{tenant_id}/sessions/{session_id}/messages", response_model=List[Dict[str, Any]])
async def get_session_messages(
    tenant_id: str,
    session_id: str
):
    """
    Get all messages for a specific session
    """
    service = DashboardService(tenant_id)
    messages = service.get_session_messages(session_id)
    return messages


@router.get("/{tenant_id}/export/csv")
async def export_analytics_csv(
    tenant_id: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    Export analytics data as CSV
    """
    from fastapi.responses import Response
    
    service = DashboardService(tenant_id)
    csv_data = service.export_analytics_csv(days)
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=analytics_{tenant_id}_{days}days.csv"
        }
    )