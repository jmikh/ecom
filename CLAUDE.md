# Shopify E-commerce Product Ingestion System

## Overview
Multi-tenant Shopify product ingestion system that fetches products from Shopify stores, processes them into a structured database, and generates semantic embeddings for search. Built with PostgreSQL + pgvector, Python, and OpenAI embeddings.

## Architecture

### Core Components

1. **Shopify Fetcher** (`src/pipeline/fetch_products.py`)
   - Fetches products from Shopify Admin API with pagination
   - Handles rate limiting (2 requests/second)
   - Extracts products, variants, images, and options
   - Saves raw data to JSON files

2. **Database Inserter** (`src/pipeline/insert_products.py`)
   - Processes JSON data into normalized database tables
   - Computes price ranges, discounts, and structured options
   - Handles products, variants, images, and embedding text
   - Uses DELETE/INSERT pattern for data consistency

3. **Embedding Generator** (`src/pipeline/generate_embeddings.py`)
   - Creates embeddings from product title, type, tags, vendor, options, description
   - Batch processing with OpenAI text-embedding-3-small model
   - Stores 1536-dimension vectors for semantic search

4. **Tenant Manager** (`src/database/manage_tenants.py`)
   - Creates, lists, and deletes tenants
   - Auto-generates UUIDs for tenant isolation
   - Manages multi-tenant data separation

5. **Pipeline Orchestrator** (`src/pipeline/ingest_shopify.py`)
   - Coordinates full pipeline: fetch → insert → embeddings
   - Supports individual operations or complete workflow
   - Validates tenant existence and JSON file requirements

### Database Schema

**Multi-tenant Architecture with Row Level Security (RLS)**

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
product_embedding_text (product_id FK, tenant_id FK, embedding_text TEXT)
product_embeddings (product_id FK, tenant_id FK, embedding VECTOR(1536))
```

**Key Features:**
- UUID-based tenant isolation for security
- CASCADE deletes maintain referential integrity
- JSONB for flexible product options storage
- pgvector for semantic search capabilities
- Comprehensive indexing for performance

## Usage

### 1. Database Setup
```bash
# Create database with pgvector extension
source venv/bin/activate
python src/database/setup.py
```

### 2. Tenant Management
```bash
# Create a new tenant
python src/database/manage_tenants.py create "Store Name"

# List all tenants
python src/database/manage_tenants.py list

# Delete tenant (WARNING: deletes all data)
python src/database/manage_tenants.py delete <tenant-uuid>
```

### 3. Product Ingestion

**Full Pipeline (Recommended):**
```bash
python src/pipeline/ingest_shopify.py \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <tenant-uuid>
```

**Individual Operations:**
```bash
# Fetch only
python src/pipeline/ingest_shopify.py --fetch-only \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <tenant-uuid>

# Insert only
python src/pipeline/ingest_shopify.py --insert-only \
  --json-file products.json \
  --tenant-id <tenant-uuid>

# Embeddings only
python src/pipeline/ingest_shopify.py --embeddings-only \
  --tenant-id <tenant-uuid>
```

**Direct Script Usage:**
```bash
# Individual components
python src/pipeline/fetch_products.py https://store.myshopify.com products.json
python src/pipeline/insert_products.py products.json --tenant-id <uuid>
python src/pipeline/generate_embeddings.py --tenant-id <uuid>
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
OPENAI_MODEL=gpt-5-mini
```

### Key Parameters
- **Embedding Batch Size**: 100 products per OpenAI API call
- **Shopify Rate Limit**: 2 requests/second (0.5s delay)
- **Embedding Model**: text-embedding-3-small (1536 dimensions)
- **Tenant Isolation**: UUID-based with RLS policies

## Data Flow

### Ingestion Pipeline
1. **Fetch**: Shopify API → JSON file
   - Paginated product retrieval
   - Rate limiting compliance
   - Complete product/variant/image data

2. **Process**: JSON → Database tables
   - Normalize Shopify data structure
   - Compute price ranges and discount flags
   - Extract options into JSONB format
   - Generate embedding text content

3. **Embed**: Text → Vector embeddings
   - Combine title, type, tags, vendor, options, description
   - Batch API calls for efficiency
   - Store vectors for similarity search

### Embedding Content Structure
```json
{
  "title": "Product Name",
  "product_type": "Category",
  "tags": "tag1, tag2, tag3",
  "vendor": "Brand Name",
  "options": {"Size": ["S", "M", "L"], "Color": ["Red", "Blue"]},
  "description": "Clean text from body_html"
}
```

## Multi-Tenant Features

### Tenant Isolation
- **Database Level**: Row Level Security policies
- **Application Level**: Tenant context setting
- **Data Integrity**: Foreign key constraints to tenants table
- **Cleanup**: CASCADE deletes when tenant removed

### Security Benefits
- UUID tenant IDs prevent enumeration attacks
- RLS ensures queries only see tenant's data
- No cross-tenant data leakage
- Secure API key management per tenant

## Performance & Monitoring

### Batch Processing
- **Products**: Processed individually with commit every 10
- **Variants**: Bulk insert via execute_batch
- **Images**: Individual inserts with FK mapping
- **Embeddings**: Batched API calls (100 products)

### Database Optimization
- **Indexes**: Strategic indexes on tenant_id, shopify_id, prices
- **JSONB**: GIN indexes on options for fast queries
- **Vectors**: IVFFlat index for similarity search
- **Foreign Keys**: Optimized CASCADE relationships

## Error Handling

### Robust Ingestion
- **API Errors**: Retry with backoff, detailed error reporting
- **Database Errors**: Transaction rollback, halt on critical failures
- **Validation**: UUID format checking, file existence verification
- **Tenant Verification**: Ensures tenant exists before processing

### Recovery Strategies
- **Partial Failures**: Individual operations can be retried
- **Data Consistency**: DELETE/INSERT ensures clean state
- **Embedding Recovery**: Regenerate embeddings without affecting products

## Files Structure
```
src/
├── database/
│   ├── setup.py              # Database schema creation
│   └── manage_tenants.py     # Tenant CRUD operations
├── pipeline/
│   ├── fetch_products.py     # Shopify API client
│   ├── insert_products.py    # Database insertion
│   ├── generate_embeddings.py # Vector generation
│   └── ingest_shopify.py     # Pipeline orchestration
└── .env                      # Configuration
```

## Development Notes

### Best Practices
- Always create tenants before ingestion
- Validate Shopify credentials in .env
- Monitor API rate limits during fetching
- Use DELETE/INSERT for data consistency
- Test with small datasets first

### Common Issues
- **403 Errors**: Check Shopify access token permissions
- **Rate Limiting**: Built-in delays handle Shopify limits
- **Memory Usage**: Large catalogs processed in batches
- **Embedding Costs**: Monitor OpenAI usage during development

### Troubleshooting
```bash
# Check tenant exists
python src/database/manage_tenants.py list

# Verify database connection
psql -h localhost -U user -d ecom_products -c "SELECT COUNT(*) FROM tenants;"

# Test Shopify connection
python src/pipeline/fetch_products.py https://store.myshopify.com test.json

# Monitor embeddings generation
tail -f embedding_logs.txt  # If logging enabled
```

## Scaling Considerations

### Multi-Store Support
- Each Shopify store gets unique tenant_id
- Isolated data processing per tenant
- Concurrent ingestion possible with different tenants

### Performance Tuning
- Adjust embedding batch sizes based on OpenAI limits
- Scale database connections for concurrent tenants
- Implement queue system for large-scale ingestion
- Consider read replicas for analytics workloads