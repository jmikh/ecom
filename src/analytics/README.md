# Analytics Module

This directory handles analytics tracking, aggregation, and reporting for the dashboard.

## Components

### 📊 `tracker.py`
**Analytics tracking with LangChain callbacks**

- **AnalyticsCallbackHandler**: LangChain callback for tracking LLM usage
  - Captures token usage from OpenAI API responses
  - Calculates costs using hardcoded pricing
  - Updates session metrics in real-time
  - Tracks: prompt tokens, completion tokens, model used, costs

- **ProductAnalyticsTracker**: Product event tracking
  - Records product recommendations
  - Tracks product inquiries
  - Logs user interactions with products
  - Provides top products analytics

### 📈 `aggregator.py`
**Dashboard metrics aggregation**

- **DashboardAggregator**: Aggregates analytics data for display
  - Overview metrics (total sessions, messages today, costs, active sessions)
  - Sessions over time with daily breakdown
  - Message volume by user/assistant
  - Cost breakdown by model
  - Intent distribution analysis
  - Hourly activity patterns

## Pricing Configuration

Hardcoded pricing per 1M tokens:
- **GPT-4o-mini**: $0.15 input / $0.60 output
- **GPT-4o**: $2.50 input / $10.00 output
- **GPT-4**: $30.00 input / $60.00 output
- **GPT-3.5-turbo**: $0.50 input / $1.50 output
- **Embedding models**: $0.02-$0.10 input

## Database Tables Used

- `chat_sessions`: Session-level metrics
- `chat_messages`: Message-level token usage
- `product_analytics`: Product event tracking

## Key Features

- **Real-time tracking**: Captures metrics as LLM calls happen
- **Cost calculation**: Automatic cost estimation based on token usage
- **Time-based aggregation**: Daily, hourly, and custom date ranges
- **Product insights**: Track which products are recommended most
- **Intent analysis**: Understand user query patterns