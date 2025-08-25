# Product Search Assistant

AI-powered product search system combining SQL filters and semantic search using PostgreSQL, pgvector, and GPT-4.

## Features

- **Dynamic Schema Inference**: Automatically infers product schema from JSON data
- **Smart Embeddings**: Creates embeddings only for high-cardinality text fields (>40 unique values)
- **Hybrid Search**: Combines structured SQL queries with semantic similarity search
- **Query Understanding**: Parses natural language into structured filters and semantic intent
- **Rank Fusion**: Intelligently merges SQL and semantic results

## Setup

### Prerequisites

- PostgreSQL 14+ with pgvector extension
- Python 3.9+
- OpenAI API key

### Installation

1. Install PostgreSQL and pgvector:
```bash
brew install postgresql
brew install pgvector
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your database credentials and OpenAI API key
```

### Database Setup

1. Create database and enable pgvector:
```bash
python src/database/setup.py
```

2. Ingest products data:
```bash
python src/pipeline/ingest.py
```

This will:
- Load products from `products.json`
- Create products table with inferred schema
- Populate metadata table with column statistics
- Generate embeddings for high-cardinality text fields

## Usage

### Start API Server

```bash
python src/api/server.py
```

Server runs on http://localhost:8000

### API Endpoints

- `POST /search` - Natural language product search
- `GET /schema` - Get database schema and metadata
- `POST /tools/sql` - Execute SQL queries
- `POST /tools/semantic` - Semantic similarity search
- `POST /tools/hybrid` - Combined SQL + semantic search
- `GET /explain?query=...` - Explain how a query is parsed

### Example Queries

```python
# Test the system
python test_search.py
```

Sample queries:
- "silver bracelets under $50"
- "comfortable yoga accessories"
- "rose gold items with good reviews"
- "products that mention family"
- "waterproof jewelry"

### Python Usage

```python
from src.agent.query_agent import QueryAgent

agent = QueryAgent()

# Search products
results = agent.search("silver bracelets under $50")

# Explain query parsing
explanation = agent.explain_search("comfortable yoga pants")

agent.close()
```

## Architecture

### Data Pipeline
1. **Schema Inference**: Analyzes JSON to determine column types
2. **Metadata Generation**: Calculates cardinality, distinct values, min/max
3. **Embedding Selection**: Marks fields with >40 unique values for embeddings
4. **Vector Generation**: Creates embeddings using OpenAI text-embedding-3-small

### Search Flow
1. **Query Parsing**: Uses GPT-4 to extract structured filters and semantic intent
2. **Hybrid Execution**: 
   - SQL queries for exact/range filters
   - Vector similarity for semantic matching
3. **Rank Fusion**: Combines results using reciprocal rank fusion
4. **Result Formatting**: Returns products with match explanations

## Configuration

### Embedding Threshold
Change cardinality threshold in `src/pipeline/ingest.py`:
```python
cardinality_threshold = 40  # Default: 40 unique values
```

### Search Weights
Adjust rank fusion weights in `src/search/tools.py`:
```python
product['combined_score'] = sql_score * 0.7 + semantic_score * 0.3
```

## Testing

Run test suite:
```bash
python test_search.py
```

This validates:
- Query parsing
- SQL filter generation
- Semantic search
- Hybrid search ranking
- Result formatting