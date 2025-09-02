# Dashboard Backend Service

This directory contains the business logic and data models for the tenant dashboard.

## Components

### 🏢 `service.py`
**Dashboard business logic service**

- **DashboardService**: Main service class for dashboard operations
  - Tenant info and settings management
  - Analytics data retrieval
  - CSV export functionality
  - Aggregates data from multiple sources

Key methods:
- `get_tenant_info()`: Fetch complete tenant information
- `update_tenant_settings()`: Update store description, brand voice, URLs
- `get_overview_metrics()`: Dashboard KPIs
- `get_sessions_over_time()`: Time-series session data
- `get_cost_breakdown()`: LLM costs by model
- `get_top_products()`: Most recommended/inquired products
- `export_analytics_csv()`: Data export for analysis

### 📝 `schemas.py`
**Pydantic models for dashboard data**

Data models:
- **TenantSettings**: Editable tenant configuration
  - Store description
  - Brand voice
  - Store/logo URLs
  - AI settings (temperature, max products)

- **DashboardMetrics**: Overview KPIs
  - Total sessions
  - Messages today
  - Cost today
  - Active sessions

- **SessionAnalytics**: Session time-series data
- **MessageVolume**: Message statistics
- **CostBreakdown**: Cost analysis by model
- **ProductEvent**: Product analytics events
- **IntentDistribution**: User intent patterns
- **HourlyActivity**: Activity by hour of day
- **TenantInfo**: Complete tenant information

## Features

- **Settings Management**: Update tenant configuration
- **Real-time Metrics**: Current activity and costs
- **Historical Analytics**: Time-series data for trends
- **Product Insights**: Track product performance
- **Cost Analysis**: Monitor LLM usage costs
- **Data Export**: CSV export for external analysis

## Integration

Works with:
- `src/analytics/aggregator.py`: Data aggregation
- `src/analytics/tracker.py`: Product event tracking
- `src/database/`: Database access
- `server/dashboard/routes.py`: API endpoints