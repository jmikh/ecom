# Source Code Directory

This directory contains the core business logic and application code for the e-commerce chat system.

## Directory Structure

### 📁 agent/
LangGraph-based chat agent implementation with intent classification and workflow routing.
- Main graph orchestration
- Intent classification (product recommendations, inquiries, store questions)
- Product search and validation logic
- Subgraph workflows for different intents

### 📁 analytics/
Analytics tracking and aggregation for dashboard metrics.
- LLM usage tracking with cost calculation
- Product event tracking (recommendations, inquiries)
- Dashboard metrics aggregation
- Session and message analytics

### 📁 dashboard/
Dashboard backend service for tenant management and analytics display.
- Tenant settings management
- Analytics data service layer
- Pydantic schemas for dashboard data models

### 📁 database/
Database connection management and data access layer.
- PostgreSQL connection pooling
- Message storage (replacing Redis)
- Session management
- Database setup and migration scripts
- Tenant management utilities

### 📁 onboarding/
Product data ingestion pipeline from Shopify.
- Shopify API product fetching
- Product data insertion to PostgreSQL
- Embedding generation for semantic search
- Pipeline orchestration

### 📁 shared/
Shared utilities and schemas used across the application.
- Pydantic models for product data
- Common types and interfaces
- Utility functions

## Key Technologies

- **LangGraph**: Workflow orchestration for chat agent
- **PostgreSQL + pgvector**: Database with vector search capabilities
- **OpenAI**: LLM for chat and embeddings
- **Pydantic**: Data validation and serialization
- **psycopg2**: PostgreSQL database driver