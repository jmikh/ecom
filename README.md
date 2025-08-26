# Shopify E-commerce Product Ingestion System

Multi-tenant system for ingesting Shopify products into a PostgreSQL database with semantic embeddings for search. Supports multiple Shopify stores with complete data isolation and vector similarity search capabilities.

## Features

- **Multi-Tenant Architecture**: Complete data isolation using UUID-based tenants with Row Level Security
- **Shopify Integration**: Full API integration with products, variants, images, and options
- **Semantic Search**: OpenAI embeddings for intelligent product search and recommendations  
- **Modular Pipeline**: Individual or complete workflow execution (fetch → insert → embeddings)
- **Robust Processing**: Error handling, rate limiting, and batch processing for reliability
- **Scalable Design**: Concurrent tenant processing with optimized database schema

## Quick Start

### Prerequisites

- PostgreSQL 14+ with pgvector extension
- Python 3.9+
- Shopify Admin API access token
- OpenAI API key

### Installation

1. **Clone and setup Python environment:**
```bash
git clone <repository-url>
cd ecom
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Install and configure PostgreSQL + pgvector:**
```bash
# macOS with Homebrew
brew install postgresql pgvector

# Start PostgreSQL service
brew services start postgresql
```

3. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required `.env` variables:
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=ecom_products

# Shopify (get from Admin → Apps → Private apps)
SHOPIFY_SHOP_URL=https://your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_API_VERSION=2025-07

# OpenAI
OPENAI_API_KEY=sk-...
```

### Setup Database

```bash
# Create database and tables
python src/database/setup.py
```

This creates:
- Database with pgvector extension
- Multi-tenant schema with RLS policies
- Optimized indexes for performance

### Create Tenant & Ingest Products

```bash
# 1. Create a tenant for your Shopify store
python src/database/manage_tenants.py create "My Store Name"

# Note the returned UUID, e.g.: a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 2. Run full ingestion pipeline
python src/pipeline/ingest_shopify.py \
  --shopify-url https://your-store.myshopify.com \
  --json-file products.json \
  --tenant-id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

That's it! Your products are now ingested with embeddings ready for search.

## Usage

### Tenant Management

```bash
# Create new tenant
python src/database/manage_tenants.py create "Store Name"

# List all tenants
python src/database/manage_tenants.py list

# Delete tenant (removes ALL data)
python src/database/manage_tenants.py delete <tenant-uuid> --force
```

### Product Ingestion Options

**Full Pipeline (Recommended):**
```bash
python src/pipeline/ingest_shopify.py \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <uuid>
```

**Individual Steps:**
```bash
# 1. Fetch products from Shopify
python src/pipeline/ingest_shopify.py --fetch-only \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <uuid>

# 2. Insert into database  
python src/pipeline/ingest_shopify.py --insert-only \
  --json-file products.json \
  --tenant-id <uuid>

# 3. Generate embeddings
python src/pipeline/ingest_shopify.py --embeddings-only \
  --tenant-id <uuid>
```

**Direct Script Usage:**
```bash
# Individual components
python src/pipeline/fetch_products.py https://store.myshopify.com products.json
python src/pipeline/insert_products.py products.json --tenant-id <uuid>
python src/pipeline/generate_embeddings.py --tenant-id <uuid> --batch-size 100
```

### Advanced Options

**Regenerate All Embeddings:**
```bash
python src/pipeline/generate_embeddings.py \
  --tenant-id <uuid> \
  --regenerate-all \
  --batch-size 50
```

**Custom Batch Sizes:**
```bash
python src/pipeline/ingest_shopify.py \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <uuid> \
  --embedding-batch-size 50
```

## Architecture

### Database Schema

The system uses a normalized, multi-tenant database schema:

```
tenants
├── tenant_id (UUID, PRIMARY KEY)
├── name (TEXT)
├── created_at, updated_at

products                           
├── id (BIGSERIAL, PRIMARY KEY)           
├── tenant_id (UUID, FK → tenants)        
├── shopify_id (BIGINT, UNIQUE)           
├── title, vendor, product_type           
├── min_price, max_price, has_discount    
├── options (JSONB)                       
├── body_html, tags, handle              

product_variants                    product_images
├── id (BIGSERIAL)                 ├── id (BIGSERIAL)
├── product_id (FK → products)     ├── product_id (FK → products)
├── tenant_id (FK → tenants)       ├── tenant_id (FK → tenants)  
├── shopify_variant_id             ├── shopify_image_id
├── price, compare_at_price        ├── src, alt, position
├── sku, barcode, inventory        ├── variant_ids (BIGINT[])
├── image_id (FK → product_images) 

product_embedding_text             product_embeddings
├── product_id (FK → products)     ├── product_id (FK → products)
├── tenant_id (FK → tenants)       ├── tenant_id (FK → tenants)
├── embedding_text (TEXT)          ├── embedding (VECTOR(1536))
├── created_at                     ├── updated_at
```

### Key Features

- **Row Level Security**: Automatic tenant isolation at database level
- **CASCADE Deletes**: Remove tenant → removes all associated data  
- **JSONB Storage**: Flexible options/metadata with fast queries
- **Vector Search**: pgvector for semantic similarity
- **Performance**: Strategic indexing on all key fields

### Data Processing Pipeline

1. **Fetch**: Shopify Admin API → JSON file
   - Handles pagination automatically
   - Respects rate limits (2 req/second)
   - Retrieves complete product hierarchy

2. **Process**: JSON → Normalized tables
   - Computes price ranges and discount flags
   - Extracts structured options from variants
   - Creates embedding text for search

3. **Embed**: Text → Vector embeddings  
   - Combines title, type, tags, vendor, options, description
   - Batched OpenAI API calls for efficiency
   - 1536-dimension vectors for similarity search

## Configuration

### Embedding Content

Each product generates embedding text containing:
```json
{
  "title": "Sterling Silver Bracelet",
  "product_type": "Jewelry", 
  "tags": "silver, bracelet, handmade",
  "vendor": "Artisan Jewelry Co",
  "options": {
    "Size": ["Small", "Medium", "Large"],
    "Style": ["Classic", "Modern"]
  },
  "description": "Beautiful handcrafted sterling silver bracelet..."
}
```

### Performance Tuning

**Batch Sizes:**
- Embedding generation: 100 products/call (adjustable)
- Database commits: Every 10 products  
- Shopify requests: 0.5s delay (rate limiting)

**Memory Usage:**
- JSON files cached during processing
- Embedding batches processed sequentially
- Database connections pooled efficiently

### Multi-Store Management

Each Shopify store gets:
- Unique tenant UUID for security
- Isolated data with no cross-contamination  
- Independent processing pipelines
- Separate embedding generation

## Error Handling & Recovery

### Robust Processing
- **API Failures**: Automatic retry with exponential backoff
- **Database Errors**: Transaction rollbacks with detailed logging
- **Partial Ingestion**: Resume from failure points
- **Validation**: UUID format, file existence, tenant verification

### Recovery Strategies
```bash
# Re-run failed embeddings only
python src/pipeline/generate_embeddings.py --tenant-id <uuid>

# Re-insert products (cleans existing data first)
python src/pipeline/insert_products.py products.json --tenant-id <uuid>

# Regenerate all embeddings from scratch
python src/pipeline/generate_embeddings.py --tenant-id <uuid> --regenerate-all
```

## Development & Testing

### Database Inspection
```bash
# Connect to database
psql -h localhost -U user -d ecom_products

# Check tenant data
SELECT t.name, COUNT(p.id) as products 
FROM tenants t 
LEFT JOIN products p ON t.tenant_id = p.tenant_id 
GROUP BY t.tenant_id, t.name;

# Check embeddings status  
SELECT COUNT(*) as products,
       COUNT(pe.product_id) as with_embeddings
FROM products p
LEFT JOIN product_embeddings pe ON p.id = pe.product_id
WHERE p.tenant_id = '<uuid>';
```

### Testing Pipeline
```bash
# Test with small dataset
python src/pipeline/ingest_shopify.py \
  --shopify-url https://demo-store.myshopify.com \
  --json-file test-products.json \
  --tenant-id <test-uuid> \
  --embedding-batch-size 10
```

### Common Issues
- **Authentication**: Verify Shopify access token has product read permissions
- **Rate Limits**: Built-in delays handle Shopify API limits
- **Large Catalogs**: Use smaller embedding batches for memory efficiency
- **Database Connections**: Ensure PostgreSQL allows sufficient connections

## Production Deployment

### Environment Setup
- Use dedicated database user with minimal permissions
- Set up connection pooling (PgBouncer recommended)
- Configure logging and monitoring
- Implement backup strategy for tenant data

### Scaling Considerations
- **Concurrent Tenants**: Process different stores simultaneously
- **Queue System**: Use Celery/RQ for large-scale ingestion
- **Read Replicas**: Separate analytics workloads
- **Caching**: Redis for frequently accessed metadata

### Security
- Store API keys in secure credential management
- Use SSL for all database connections  
- Implement audit logging for tenant operations
- Regular security updates for dependencies

## License

[Your License Here]

## Support

For issues and questions:
- Check troubleshooting section in CLAUDE.md
- Review error logs for specific failure details
- Ensure all dependencies are correctly installed