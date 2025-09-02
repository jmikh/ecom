# E-commerce AI Chat System with Product Recommendations

## Overview
Multi-tenant e-commerce system combining Shopify product ingestion, AI-powered chat interface, and intelligent product recommendations. Built with PostgreSQL + pgvector for semantic search, LangGraph for conversational AI, FastAPI for the web server, and TypeScript for type-safe frontend development.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Home Page   │  │ Chat Widget  │  │  TypeScript      │  │
│  │  (index.html)│  │ (widget.js)  │  │  Types (.ts)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼───────────────────────────────────┐
│                      FastAPI Server                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Routes     │  │ Chat Service │  │     Auth         │  │
│  │  (app.py)    │  │              │  │   (tenant)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    LangGraph Agent                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Intent     │  │   Product    │  │   Validation     │  │
│  │ Classifier   │  │   Search     │  │     Node         │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Data Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL  │  │    Redis     │  │   Embeddings     │  │
│  │  + pgvector  │  │  (sessions)  │  │    (OpenAI)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Project Structure

```
ecom/
├── src/
│   ├── agent/                      # LangGraph AI Agent
│   │   ├── main_graph.py           # Main workflow orchestrator
│   │   ├── graph_state.py          # State management
│   │   ├── config.py               # Agent configuration
│   │   ├── classify_intent_node.py # Intent classification
│   │   ├── get_product_filters_node.py      # Extract search filters
│   │   ├── fetch_candidate_products_node.py # Database search
│   │   ├── validate_recommended_products_node.py # LLM validation
│   │   ├── product_recommendation_graph.py  # Recommendation subgraph
│   │   ├── product_inquiry_graph.py        # Product Q&A subgraph
│   │   ├── store_brand_graph.py            # Store info subgraph
│   │   ├── unrelated_graph.py              # Fallback subgraph
│   │   └── error_node.py                   # Error handling
│   │
│   ├── database/                   # Database Layer
│   │   ├── __init__.py            # Connection pool management
│   │   ├── setup.py               # Schema creation
│   │   └── manage_tenants.py     # Tenant CRUD operations
│   │
│   ├── pipeline/                   # Data Ingestion Pipeline
│   │   ├── fetch_products.py     # Shopify API client
│   │   ├── insert_products.py    # Database insertion
│   │   ├── generate_embeddings.py # Vector generation
│   │   └── ingest_shopify.py     # Pipeline orchestrator
│   │
│   └── shared/                     # Shared Components
│       ├── schemas.py             # Pydantic models (ProductCard, etc.)
│       └── __init__.py
│
├── server/                         # Web Server
│   ├── app.py                    # FastAPI application & routes
│   ├── auth.py                   # Tenant authentication
│   ├── chat_service.py           # Chat processing & SSE streaming
│   ├── config.py                 # Server configuration
│   ├── models.py                 # Request/Response models
│   │
│   └── static/                    # Frontend Assets
│       ├── index.html            # E-commerce home page
│       ├── widget.js             # Embeddable chat widget
│       ├── types.ts              # TypeScript interfaces (generated)
│       ├── widget-typed.ts       # TypeScript widget implementation
│       ├── test_page.html        # Widget test page
│       ├── typed-example.html    # TypeScript demo page
│       └── tsconfig.json         # TypeScript configuration
│
├── tests/                          # Test Files
│   ├── test_widget.py            # Widget interaction tests
│   ├── test_widget_mens.py       # Category search tests
│   └── test_homepage.py          # Home page tests
│
├── scripts/                        # Utility Scripts
│   ├── generate_types.py         # Generate TypeScript from Pydantic
│   └── all_models.py             # Consolidated models for TS generation
│
├── run_server.py                  # Server entry point
├── requirements.txt               # Python dependencies
├── .env                          # Environment configuration
└── CLAUDE.md                     # This documentation

```

## Core Features

### 1. **Product Ingestion Pipeline**
- Fetches products from Shopify stores
- Normalizes data into PostgreSQL tables
- Generates semantic embeddings for search
- Multi-tenant data isolation

### 2. **AI Chat Agent (LangGraph)**
- **Intent Classification**: Routes queries to appropriate workflows
- **Product Recommendations**: Semantic + filter-based search
- **Structured Responses**: Returns typed ProductCard objects
- **Context Management**: Maintains conversation history

### 3. **Web Server (FastAPI)**
- **Endpoints**:
  - `GET /` - Home page with product catalog
  - `POST /api/session` - Session management
  - `POST /api/chat/stream` - SSE streaming chat
  - `GET /api/products/{tenant_id}` - Product listing
  - `GET /api/chat/history/{session_id}` - Chat history
- **Features**:
  - Server-Sent Events for real-time streaming
  - Redis session storage
  - Multi-tenant support
  - CORS configuration

### 4. **Frontend Components**
- **Home Page**: Product grid with filtering/sorting
- **Chat Widget**: Embeddable customer support interface
- **TypeScript Types**: Generated from Pydantic models
- **Product Cards**: Rich media display with images/prices

## Database Schema

### Multi-tenant Architecture with Row Level Security (RLS)

```sql
-- Tenant isolation
tenants (tenant_id UUID PRIMARY KEY, name TEXT, created_at, updated_at)

-- Product hierarchy
products (id, tenant_id FK, shopify_id, title, vendor, product_type, 
         min_price, max_price, has_discount, options JSONB, ...)
         
product_variants (id, product_id FK, tenant_id FK, shopify_variant_id,
                 price, compare_at_price, sku, options, image_id FK, ...)
                 
product_images (id, product_id FK, tenant_id FK, shopify_image_id,
               src, alt, position, variant_ids[], ...)

-- Embedding system
product_embeddings (product_id FK, tenant_id FK, embedding VECTOR(1536))
```

## Configuration

### Environment Variables (.env)
```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=ecom_products

# Shopify Configuration
SHOPIFY_SHOP_URL=https://store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_API_VERSION=2025-07

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# LangSmith (Optional)
LANGSMITH_API_KEY=ls_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ecom-product-agent
```

## Usage

### 1. Database Setup
```bash
# Create database with pgvector extension
python src/database/setup.py

# Create a tenant
python src/database/manage_tenants.py create "Store Name"
# Returns: tenant_id (UUID)
```

### 2. Product Ingestion
```bash
# Full pipeline
python src/pipeline/ingest_shopify.py \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <tenant-uuid>

# Or individual steps
python src/pipeline/fetch_products.py <shopify-url> <output.json>
python src/pipeline/insert_products.py <input.json> --tenant-id <uuid>
python src/pipeline/generate_embeddings.py --tenant-id <uuid>
```

### 3. Start Server
```bash
# Development server with auto-reload
python run_server.py

# Access at:
# - Home: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Test Page: http://localhost:8000/static/test_page.html
```

### 4. Embed Chat Widget
```html
<!-- Add to any website -->
<script src="http://localhost:8000/static/widget.js" 
        data-tenant-id="YOUR-TENANT-UUID">
</script>
```

## TypeScript Integration

### Generate Types from Pydantic Models
```bash
# Install dependencies
npm install -g json-schema-to-typescript
pip install pydantic-to-typescript

# Generate TypeScript interfaces
pydantic2ts --module ./all_models.py --output server/static/types.ts

# Compile TypeScript
cd server/static && npx tsc
```

### Benefits
- **Type Safety**: Catch errors at compile time
- **IDE Support**: Full autocomplete for API calls
- **Single Source of Truth**: Backend models define the contract
- **Type Guards**: Runtime validation of API responses

## LangGraph Agent Workflow

### Main Graph Flow
```
User Message
    ↓
Classify Intent
    ↓
┌─────────────────────────────────┐
│  Route by Intent                │
├─────────────────────────────────┤
│ • PRODUCT_RECOMMENDATION        │ → Get Filters → Fetch Products → Validate
│ • PRODUCT_INQUIRY               │ → Product Q&A Handler
│ • STORE_BRAND                   │ → Store Info Handler  
│ • UNRELATED                     │ → Fallback Response
└─────────────────────────────────┘
    ↓
Return Response
```

### Product Recommendation Pipeline
1. **Extract Filters**: Parse user query for product criteria
2. **Database Search**: Combined SQL filters + semantic search
3. **LLM Validation**: Rank and explain recommendations
4. **Structured Response**: Return ProductCard[] with reasoning

## Testing

### Browser Automation (Playwright)
```bash
# Install Playwright
pip install playwright
playwright install chromium

# Run tests
python test_widget.py         # Test chat interaction
python test_homepage.py       # Test product display
python test_widget_mens.py    # Test category filtering
```

### Manual Testing
1. Open http://localhost:8000
2. Browse products with filters
3. Click chat widget button
4. Try queries like:
   - "Show me outdoor gear under $50"
   - "I need camping equipment"
   - "What shirts do you have?"

## Performance Optimizations

- **Connection Pooling**: Database connections reused
- **Batch Processing**: Embeddings generated in batches of 100
- **Caching**: Redis session cache (1 hour TTL)
- **Streaming**: SSE for real-time responses
- **Lazy Loading**: Products fetched on demand
- **Vector Indexing**: IVFFlat index for similarity search

## Security Features

- **Multi-tenant Isolation**: UUID-based tenant separation
- **Row Level Security**: PostgreSQL RLS policies
- **Session Management**: Secure cookie-based sessions
- **Input Validation**: Pydantic models validate all inputs
- **CORS Configuration**: Controlled cross-origin access
- **Environment Variables**: Secrets kept out of code

## Common Operations

### View Logs
```bash
# Server logs
tail -f server.log

# LangSmith traces (if configured)
# Visit: https://smith.langchain.com
```

### Database Queries
```sql
-- Count products per tenant
SELECT tenant_id, COUNT(*) FROM products GROUP BY tenant_id;

-- Check embeddings
SELECT COUNT(*) FROM product_embeddings WHERE embedding IS NOT NULL;

-- View product types
SELECT DISTINCT product_type FROM products WHERE tenant_id = '...';
```

### Troubleshooting
- **403 Errors**: Check Shopify access token
- **No Products**: Verify tenant_id exists
- **Chat Not Working**: Check Redis is running
- **Type Errors**: Regenerate TypeScript types

## Future Enhancements

- [ ] User authentication & accounts
- [ ] Order processing integration
- [ ] Advanced analytics dashboard
- [ ] Mobile app support
- [ ] Real-time inventory updates
- [ ] Multi-language support
- [ ] A/B testing for recommendations
- [ ] Custom training for product matching

## Development Notes

### Best Practices
- Always create tenants before ingestion
- Test with small datasets first
- Monitor OpenAI API usage
- Use TypeScript for new frontend code
- Keep Pydantic models as source of truth

### Key Technologies
- **Backend**: Python, FastAPI, LangGraph, Pydantic
- **Frontend**: TypeScript, Server-Sent Events
- **Database**: PostgreSQL, pgvector, Redis
- **AI/ML**: OpenAI GPT-4o-mini, text-embedding-3-small
- **Testing**: Playwright, pytest
- **DevOps**: Docker-ready, environment-based config