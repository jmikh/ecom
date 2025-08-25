from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.agent.query_agent import QueryAgent
from src.search.tools import SearchTools
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Product Search Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

query_agent = QueryAgent()
search_tools = SearchTools()

class SearchRequest(BaseModel):
    query: str
    mode: Optional[str] = "hybrid"
    limit: Optional[int] = 20

class SQLRequest(BaseModel):
    query: str
    params: Optional[List[Any]] = None

class SemanticSearchRequest(BaseModel):
    query: str
    fields: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    k: Optional[int] = 20

@app.get("/")
async def root():
    return {
        "message": "Product Search Assistant API",
        "endpoints": [
            "/search - Natural language product search",
            "/schema - Get database schema information",
            "/tools/sql - Execute SQL queries",
            "/tools/semantic - Semantic search",
            "/tools/hybrid - Hybrid search",
            "/explain - Explain query parsing"
        ]
    }

@app.post("/search")
async def search(request: SearchRequest):
    try:
        results = query_agent.search(
            request.query,
            mode=request.mode
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema")
async def get_schema():
    try:
        schema = search_tools.describe_schema()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/sql")
async def run_sql(request: SQLRequest):
    try:
        results = search_tools.run_sql(
            request.query,
            tuple(request.params) if request.params else None
        )
        return {
            "results": results,
            "count": len(results)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/semantic")
async def semantic_search(request: SemanticSearchRequest):
    try:
        results = search_tools.semantic_search(
            query=request.query,
            fields=request.fields,
            filters=request.filters,
            k=request.k
        )
        return {
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/hybrid")
async def hybrid_search(request: SemanticSearchRequest):
    try:
        results = search_tools.hybrid_search(
            query=request.query,
            filters=request.filters,
            k=request.k
        )
        return {
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/explain")
async def explain_query(query: str = Query(..., description="The search query to explain")):
    try:
        explanation = query_agent.explain_search(query)
        return {
            "query": query,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    query_agent.close()
    search_tools.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)