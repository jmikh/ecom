# Tenant Dashboard

## Overview
The tenant dashboard provides analytics and configuration management for e-commerce store owners.

## Features

### Store Configuration
- **Store Description**: Edit your store's description
- **Brand Voice**: Define your AI assistant's personality and tone
- **Store URL**: Set your store's main website
- **Logo URL**: Add your store logo
- **AI Settings**: Configure temperature and max products shown

### Analytics Overview
- **Total Sessions**: All-time chat sessions
- **Messages Today**: Daily message count
- **Cost Today**: LLM usage costs for the day
- **Active Sessions**: Sessions in the last hour

### Visualizations
- **Sessions Over Time**: Line chart showing session trends
- **Message Volume**: Bar chart of user vs assistant messages
- **Cost Breakdown**: Donut chart showing costs by model
- **Hourly Activity**: Activity patterns throughout the day

### Product Analytics
- **Top Recommended Products**: Most frequently recommended items
- **Product Inquiries**: Products users ask about most
- **Event Tracking**: Recommendations, inquiries, and clicks

### Session Details
- **Recent Sessions**: View latest chat sessions
- **Session Metrics**: Duration, message count, costs
- **Export Data**: Download analytics as CSV

## Access

Open the dashboard at:
```
http://localhost:8000/static/dashboard.html?tenant_id=YOUR_TENANT_ID
```

## API Endpoints

### Configuration
- `GET /api/dashboard/{tenant_id}/info` - Get tenant information
- `PUT /api/dashboard/{tenant_id}/settings` - Update tenant settings

### Analytics
- `GET /api/dashboard/{tenant_id}/overview` - Overview metrics
- `GET /api/dashboard/{tenant_id}/sessions?days=7` - Sessions over time
- `GET /api/dashboard/{tenant_id}/messages?days=7` - Message volume
- `GET /api/dashboard/{tenant_id}/costs?days=7` - Cost breakdown
- `GET /api/dashboard/{tenant_id}/products/top?event_type=recommended&days=7` - Top products
- `GET /api/dashboard/{tenant_id}/activity/hourly` - Hourly activity pattern
- `GET /api/dashboard/{tenant_id}/sessions/recent` - Recent sessions
- `GET /api/dashboard/{tenant_id}/export/csv?days=30` - Export CSV

## Implementation Details

### Backend Components
- **DashboardService** (`src/dashboard/service.py`): Business logic
- **DashboardAggregator** (`src/analytics/aggregator.py`): Metrics aggregation
- **AnalyticsCallbackHandler** (`src/analytics/tracker.py`): LLM usage tracking
- **MessageStore** (`src/database/message_store.py`): PostgreSQL message storage

### Database Tables
- **chat_sessions**: Session metadata and costs
- **chat_messages**: Message history with token usage
- **product_analytics**: Product event tracking
- **tenants**: Extended with brand_voice, store_url, logo_url, settings

### Frontend
- **Chart.js**: Data visualization
- **Responsive Design**: Works on desktop and mobile
- **Real-time Updates**: Auto-refresh every 30 seconds
- **Date Filtering**: 7, 30, 90 day views

## Usage Flow

1. **Chat Activity**: Users interact with the chat widget
2. **Analytics Tracking**: LangChain callbacks track LLM usage
3. **Data Storage**: Metrics stored in PostgreSQL
4. **Aggregation**: Dashboard service aggregates data
5. **Visualization**: Frontend displays charts and tables

## Cost Tracking

LLM costs are calculated using hardcoded pricing:
- GPT-4o-mini: $0.15/$0.60 per 1M tokens (input/output)
- GPT-4o: $2.50/$10.00 per 1M tokens
- GPT-4: $30.00/$60.00 per 1M tokens
- GPT-3.5-turbo: $0.50/$1.50 per 1M tokens
- Embedding models: $0.02-$0.10 per 1M tokens

## Future Enhancements

- Authentication and multi-user support
- Custom date ranges
- Advanced filtering and search
- Email reports and alerts
- A/B testing for AI responses
- Conversion tracking
- Customer satisfaction metrics