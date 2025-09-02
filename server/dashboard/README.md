# Dashboard API Routes

This directory contains the FastAPI routes for the dashboard API endpoints.

## Component

### 🛣️ `routes.py`
**RESTful API endpoints for dashboard**

Provides HTTP endpoints for all dashboard functionality, connecting the frontend to the backend services.

## API Endpoints

### Tenant Management
- **GET** `/api/dashboard/{tenant_id}/info`
  - Get complete tenant information
  - Returns: name, description, brand_voice, settings
  
- **PUT** `/api/dashboard/{tenant_id}/settings`
  - Update tenant configuration
  - Body: TenantSettings model
  - Updates: description, brand_voice, URLs, AI settings

### Analytics Endpoints

#### Overview
- **GET** `/api/dashboard/{tenant_id}/overview`
  - Returns: total_sessions, messages_today, cost_today, active_sessions

#### Time Series
- **GET** `/api/dashboard/{tenant_id}/sessions?days=7`
  - Sessions over time with daily breakdown
  - Query params: days (1-90)
  
- **GET** `/api/dashboard/{tenant_id}/messages?days=7`
  - Message volume by role
  - Query params: days (1-90)

#### Cost Analysis
- **GET** `/api/dashboard/{tenant_id}/costs?days=7`
  - Cost breakdown by model
  - Returns: models array, total_cost, period_days
  - Query params: days (1-90)

#### Product Analytics
- **GET** `/api/dashboard/{tenant_id}/products/top?event_type=recommended&days=7`
  - Top products by event type
  - Query params:
    - event_type: recommended|inquired|clicked
    - limit: 1-100
    - days: 1-90

#### User Behavior
- **GET** `/api/dashboard/{tenant_id}/intents?days=7`
  - Distribution of user intents
  - Query params: days (1-90)
  
- **GET** `/api/dashboard/{tenant_id}/activity/hourly`
  - Hourly activity pattern (last 7 days)

#### Session Details
- **GET** `/api/dashboard/{tenant_id}/sessions/recent?limit=10`
  - Recent chat sessions with metrics
  - Query params: limit (1-100)

#### Data Export
- **GET** `/api/dashboard/{tenant_id}/export/csv?days=30`
  - Export analytics as CSV
  - Query params: days (1-365)
  - Returns: CSV file download

## Response Models

All endpoints return typed responses using Pydantic models from `src/dashboard/schemas.py`:
- TenantInfo
- DashboardMetrics
- SessionAnalytics
- MessageVolume
- CostBreakdown
- ProductEvent
- IntentDistribution
- HourlyActivity

## Error Handling

- 404: Tenant not found
- 500: Server/database errors
- Validation errors return 422 with details

## Integration

This module connects:
- **Frontend**: Dashboard HTML/JavaScript
- **Service Layer**: DashboardService
- **Database**: Via service layer
- **FastAPI**: Registered in main app router