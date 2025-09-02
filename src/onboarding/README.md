# Product Onboarding Pipeline

This directory contains the Shopify product ingestion pipeline for importing products into the database.

## Pipeline Components

### 🔄 `ingest_shopify.py`
**Main pipeline orchestrator**
- Coordinates the complete ingestion workflow
- Supports full pipeline or individual operations
- Command-line interface for automation
- Validates tenant existence

Usage:
```bash
python ingest_shopify.py \
  --shopify-url https://store.myshopify.com \
  --json-file products.json \
  --tenant-id <uuid>
```

### 📥 `fetch_products.py`
**Shopify API product fetcher**
- Fetches products from Shopify Admin API
- Handles pagination automatically
- Rate limiting (2 requests/second)
- Extracts products, variants, images, options
- Saves to JSON for processing

Features:
- Complete product data extraction
- Variant details with pricing
- Image URLs and associations
- Product options and values

### 💾 `insert_products.py`
**Database insertion module**
- Processes JSON data into PostgreSQL
- Normalizes Shopify data structure
- Computes price ranges and discounts
- Handles DELETE/INSERT for consistency

Tables populated:
- `products`: Main product records
- `product_variants`: SKU variations
- `product_images`: Media assets
- `product_embedding_text`: Text for embeddings

### 🧮 `generate_embeddings.py`
**Semantic search embedding generator**
- Creates embeddings from product data
- Uses OpenAI text-embedding-3-small
- Batch processing (100 products/call)
- 1536-dimension vectors

Embedding content includes:
- Product title
- Product type
- Tags
- Vendor
- Options
- Description (cleaned HTML)

## Data Flow

1. **Fetch**: Shopify API → JSON file
2. **Insert**: JSON → PostgreSQL tables
3. **Embed**: Product text → Vector embeddings

## Configuration

Required environment variables:
```
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_API_VERSION=2025-07
OPENAI_API_KEY=sk-...
```

## Best Practices

- Always create tenant first
- Test with small product sets
- Monitor API rate limits
- Use DELETE/INSERT for updates
- Validate embeddings after generation

## Error Handling

- Automatic retry with backoff
- Transaction rollback on failure
- Detailed error logging
- Partial failure recovery