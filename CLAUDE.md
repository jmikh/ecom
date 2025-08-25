# E-commerce Product Search Assistant

## Overview
AI-powered assistant that answers natural-language queries about a product catalog using hybrid search combining SQL filters and semantic similarity. Built with PostgreSQL + pgvector, Python, and OpenAI embeddings.

## Architecture

### Core Components

1. **Query Parser** (`src/agent/query_agent.py`)
   - Uses LLM (gpt-4o-mini or gpt-5-mini) to parse natural language queries
   - Extracts structured filters (category, price, etc.) and semantic query
   - Cleans filters based on available schema columns

2. **Search Tools** (`src/search/tools.py`)
   - `hybrid_search()`: Combines SQL filtering with semantic search
   - `semantic_search()`: Vector similarity search using pgvector
   - Deduplicates results by product, keeping best score per product
   - Returns top k=20 products by default

3. **Ingestion Pipeline** (`src/pipeline/ingest.py`)
   - Dynamically infers schema from products.json
   - Creates embeddings for high-cardinality fields (>40 unique values)
   - Batches embedding generation by field (100 products per API call)
   - Updates metadata table with column statistics

### Database Schema

**products table**: Dynamic schema based on JSON data
- Text fields: category, product_name, material, etc.
- Array fields: options, reviews
- Numeric fields: price, review_avg_score

**embeddings table**:
- product_id (FK)
- field (which field was embedded)
- embedding (vector 1536 dimensions)

**metadata table**:
- column_name, data_type
- is_low_cardinality (≤40 distinct values)
- distinct_values (for low-cardinality fields)
- min_value, max_value (for numeric fields)

## Search Flow

1. **Query Parsing**
   - LLM extracts filters and semantic query
   - Filters cleaned against schema (removes non-existent columns)

2. **Hybrid Search**
   - SQL count for logging
   - Semantic search with SQL prefiltering
   - Deduplication by product ID
   - Returns top 100 products

3. **LLM Filtering** (final step)
   - Takes top 5 products
   - LLM evaluates each with rank and reason
   - Returns max 3 best matches

## Key Improvements Made

### Array Field Handling
- Fixed PostgreSQL array overlap operator (`&&`) for array columns
- Proper IN clause for text columns
- Prevents "operator does not exist" errors

### Semantic Search Deduplication
- Searches across ALL embedding fields
- Keeps best score per product (not per embedding)
- Prevents duplicate products in results

### Numeric Field Support
- Added numeric fields to metadata table
- Stores min/max values for range queries
- Enables price filtering

### Mock Modes
- Embedding mock mode: Uses zero vectors to avoid API costs
- Query parser mock mode: Prints OpenAI requests without sending

## Configuration

### Environment Variables (.env)
```
DB_NAME=ecom_products
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # or gpt-5-mini
```

### Key Parameters
- Cardinality threshold: 40 (for low/high cardinality decision)
- Embedding dimensions: 1536 (text-embedding-3-small)
- Batch size: 100 products per embedding API call
- Default search limit: 20 products
- LLM filtering: Top 5 → Max 3 results

## Testing Tools

**test_agent.py**: Full search pipeline testing
```bash
python test_agent.py "colorful bracelets"
python test_agent.py --interactive
python test_agent.py --examples --mock
```

**test_similarity.py**: Direct embedding similarity testing
```bash
python test_similarity.py "silver" --field combined
python test_similarity.py "silver" --compare-fields
```

## Common Issues & Solutions

### "Live Life In Full Color" not appearing
- Caused by semantic search returning embeddings, not products
- Fixed by deduplicating by product ID

### Price filter being removed
- Numeric fields weren't in metadata table
- Fixed by processing numeric fields during ingestion

### SQL operator errors
- Array fields need `&&` operator, not `IN`
- Fixed by checking column type before building WHERE clause

### NoneType similarity scores
- Some embeddings returned NULL scores
- Fixed by checking for None before formatting

## Search Funnel Logging

Tracks product counts at each stage:
1. Total products in database
2. SQL filtered results
3. Semantic search results
4. Combined & ranked results
5. Pre-LLM filtering (top 5)
6. Final results after LLM filtering

## Usage Examples

### Running Components
```bash
# Ingest products with embeddings
python src/pipeline/ingest.py

# Mock mode (no API calls)
python src/pipeline/ingest.py --mock

# Test search interactively
python test_agent.py --interactive

# Test specific queries
python test_agent.py "red silk dress under $100"
python test_agent.py "comfortable workout clothes"

# Debug similarity scores
python test_similarity.py "silver jewelry" --field combined
```

## Files Structure
```
src/
├── agent/query_agent.py      # Main query processing & orchestration
├── search/tools.py           # Core search functions & database queries  
├── pipeline/ingest.py        # Data ingestion & embedding generation
test_agent.py                 # Full pipeline testing tool
test_similarity.py            # Embedding similarity debugging
products.json                 # Input product catalog
schema.sql                    # Database schema definitions
```

## Performance & Monitoring
- **Search Funnel Logging**: Tracks product counts through each filter stage
- **Embedding Efficiency**: ~460 embeddings in 5 API calls (100 products/call)
- **Result Limits**: 20 semantic results → 5 for LLM → max 3 final results
- **Rate Limiting**: 1 second between OpenAI API calls

## Development Notes
- Always test with mock mode first to avoid API costs
- Re-run ingestion after schema changes to update metadata
- Use similarity testing to debug unexpected search results
- Check logs for search funnel metrics to understand filtering