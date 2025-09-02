# Database Layer

This directory manages all database operations, connections, and schema management.

## Core Components

### 🔌 `database_pool.py`
**Connection pool manager for PostgreSQL**
- Thread-safe connection pooling (2-10 connections)
- Automatic connection reuse and cleanup
- Tenant isolation with Row Level Security
- Methods: `run_read()`, `run_write()`
- Environment-based configuration

### 💬 `message_store.py`
**Message and session storage (PostgreSQL-based)**
- **MessageStore**: Async message storage
  - Store chat messages with metadata
  - Track token usage and costs
  - Conversation context retrieval
  
- **SessionManager**: Chat session management
  - Create/update sessions
  - Track session metrics
  - Session cleanup
  
- **ConversationMemory**: Backward compatibility wrapper
  - Bridge for legacy Redis interface
  - Synchronous message operations

### 🚀 `setup.py`
**Database schema initialization**
- Creates all required tables
- Sets up pgvector extension
- Configures indexes
- Row Level Security policies

Tables created:
- `tenants`: Multi-tenant configuration
- `products`: Product catalog
- `product_variants`: Product variations
- `product_images`: Product media
- `product_embeddings`: Vector search
- `chat_sessions`: Session tracking
- `chat_messages`: Message history
- `product_analytics`: Event tracking

### 👥 `manage_tenants.py`
**Tenant CRUD operations**
- Create new tenants with UUID
- List all tenants
- Delete tenants (cascades all data)
- Command-line interface

### 📊 `migrate_dashboard.py`
**Dashboard feature migration**
- Adds dashboard columns to tenants table
- Creates analytics tables
- Safe migration with existence checks

### 🔄 `redis_manager.py`
**Legacy Redis session management**
- Still used for session state
- Will be fully replaced by PostgreSQL
- Maintains backward compatibility

## Database Schema

### Multi-Tenant Architecture
- UUID-based tenant isolation
- Row Level Security (RLS)
- CASCADE deletes for data integrity

### Key Features
- **pgvector**: Semantic search with embeddings
- **JSONB**: Flexible product options storage
- **Connection pooling**: Efficient resource usage
- **Transaction support**: Data consistency

## Environment Variables

Required in `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecom_products
DB_USER=your_user
DB_PASSWORD=your_password
```

## Usage

```python
from src.database import get_database

db = get_database()
results = db.run_read(
    "SELECT * FROM products WHERE tenant_id = %s",
    (tenant_id,),
    tenant_id=tenant_id
)
```