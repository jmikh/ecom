# FastAPI Web Server

This directory contains the FastAPI web server that serves the chat API and web interfaces.

## Core Components

### 🚀 `app.py`
**Main FastAPI application**
- CORS configuration for cross-origin requests
- Static file serving
- Exception handling
- Lifecycle management
- Router registration

Endpoints:
- `GET /`: Home page
- `POST /api/session`: Create/validate session
- `POST /api/chat`: Synchronous chat
- `POST /api/chat/stream`: Server-sent events streaming
- `GET /api/chat/history/{session_id}`: Chat history
- `GET /api/products/{tenant_id}`: Product catalog

### 💬 `chat_service.py`
**Chat service integration layer**
- Bridges web requests with LangGraph agent
- Session management
- Message processing
- Analytics integration
- Response streaming

Key features:
- Product card detection and formatting
- PostgreSQL message storage
- Analytics callback integration
- Error handling

### 📝 `models.py`
**Pydantic models for API**
- Request/response validation
- Type safety for endpoints
- Error response formatting

Models:
- `ChatRequest`: Incoming chat message
- `ChatResponse`: Chat reply
- `SessionRequest`: Session creation
- `SessionResponse`: Session details
- `ErrorResponse`: Error formatting

### 🔒 `auth.py`
**Authentication and authorization**
- Tenant verification
- Rate limiting (currently disabled)
- Database tenant validation

### ⚙️ `config.py`
**Server configuration**
- API host/port settings
- CORS configuration
- Session timeout
- Rate limiting settings

## Subdirectories

### 📁 `dashboard/`
Dashboard API routes and logic

### 📁 `static/`
Frontend files and assets

## Features

- **Streaming Chat**: Real-time responses via SSE
- **Multi-tenant**: Tenant isolation and validation
- **Session Management**: Persistent chat sessions
- **Error Handling**: Graceful error responses
- **CORS Support**: Cross-origin API access
- **Static Serving**: Widget and web pages

## Configuration

Environment variables:
```
API_HOST=0.0.0.0
API_PORT=8000
SESSION_TIMEOUT_MINUTES=60
```

## Running the Server

```bash
python run_server.py
```

Access points:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Dashboard: http://localhost:8000/static/dashboard.html
- Home: http://localhost:8000