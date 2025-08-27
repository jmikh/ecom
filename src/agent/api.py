"""
FastAPI server for Product Recommendation Agent
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
import asyncio

from .product_agent import ProductAgent
from .memory import SessionManager
from .config import config


# Initialize FastAPI app
app = FastAPI(
    title="Product Recommendation Agent",
    description="AI-powered product search and recommendation system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session manager
session_manager = SessionManager()

# Agent cache (simple in-memory cache for demo - use Redis in production)
agent_cache: Dict[str, ProductAgent] = {}


# Request/Response models
class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    tenant_id: str = Field(..., description="Tenant ID")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID for future requests")
    products: Optional[List[Dict[str, Any]]] = Field(None, description="Recommended products")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SessionInfo(BaseModel):
    session_id: str
    tenant_id: str
    created_at: str
    last_active: str
    message_count: int
    viewed_products_count: int


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    tenant_id: str = Field(..., description="Tenant ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters")
    limit: int = Field(20, description="Number of results")


# Helper functions
def get_or_create_agent(tenant_id: str, session_id: Optional[str] = None) -> tuple[ProductAgent, str]:
    """Get existing agent or create new one"""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    cache_key = f"{tenant_id}:{session_id}"
    
    if cache_key not in agent_cache:
        agent_cache[cache_key] = ProductAgent(tenant_id, session_id)
    
    return agent_cache[cache_key], session_id


def cleanup_old_agents():
    """Clean up old agents from cache (run periodically)"""
    # Simple cleanup - in production, use TTL-based cleanup
    if len(agent_cache) > 100:
        # Keep only 50 most recent
        keys = list(agent_cache.keys())[:50]
        for key in keys:
            del agent_cache[key]


# API Endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint for product recommendations
    """
    try:
        # Get or create agent
        agent, session_id = get_or_create_agent(request.tenant_id, request.session_id)
        
        # Process message
        response = await agent.chat(request.message)
        
        # Get current products from agent state if any
        products = None
        if hasattr(agent, 'current_products'):
            products = agent.current_products
        
        # Build response
        return ChatResponse(
            response=response,
            session_id=session_id,
            products=products,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "model": config.openai_model,
                "tenant_id": request.tenant_id
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_products(request: SearchRequest):
    """
    Direct product search endpoint
    """
    try:
        from .tools.database_tools import DatabaseTools
        
        db_tools = DatabaseTools(request.tenant_id)
        
        # Perform search based on query type
        if request.filters:
            # SQL search with filters
            results = db_tools.sql_search(request.filters, request.limit)
        else:
            # Semantic search
            results = db_tools.semantic_search(request.query, request.limit)
        
        return {
            "query": request.query,
            "results": results,
            "count": len(results),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tenant_id": request.tenant_id
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
async def get_session_info(session_id: str, tenant_id: str = Header(...)):
    """
    Get session information
    """
    try:
        session_data = session_manager.get_session_data(session_id, tenant_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get conversation history
        from .memory import ConversationMemory
        memory = ConversationMemory(session_id, tenant_id)
        history = memory.get_conversation_history()
        
        return SessionInfo(
            session_id=session_id,
            tenant_id=tenant_id,
            created_at=session_data.get("created_at", ""),
            last_active=session_data.get("last_active", ""),
            message_count=len(history),
            viewed_products_count=len(session_data.get("viewed_products", []))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
async def clear_session(session_id: str, tenant_id: str = Header(...)):
    """
    Clear a session
    """
    try:
        session_manager.clear_session(session_id, tenant_id)
        
        # Remove from agent cache
        cache_key = f"{tenant_id}:{session_id}"
        if cache_key in agent_cache:
            del agent_cache[cache_key]
        
        return {"message": "Session cleared successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions(tenant_id: str = Header(...)):
    """
    List active sessions for a tenant
    """
    try:
        sessions = session_manager.get_active_sessions(tenant_id)
        
        session_list = []
        for session_id in sessions:
            session_data = session_manager.get_session_data(session_id, tenant_id)
            if session_data:
                session_list.append({
                    "session_id": session_id,
                    "last_active": session_data.get("last_active"),
                    "created_at": session_data.get("created_at")
                })
        
        return {
            "sessions": session_list,
            "count": len(session_list)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}")
async def get_product_details(product_id: int, tenant_id: str = Header(...)):
    """
    Get detailed product information
    """
    try:
        from .tools.database_tools import DatabaseTools
        
        db_tools = DatabaseTools(tenant_id)
        products = db_tools.get_product_details([product_id])
        
        if not products:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return products[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}/similar")
async def get_similar_products(
    product_id: int, 
    tenant_id: str = Header(...),
    limit: int = 10
):
    """
    Get products similar to a given product
    """
    try:
        from .tools.database_tools import DatabaseTools
        
        db_tools = DatabaseTools(tenant_id)
        similar = db_tools.get_similar_products(product_id, limit)
        
        return {
            "product_id": product_id,
            "similar_products": similar,
            "count": len(similar)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema")
async def get_schema(tenant_id: str = Header(...)):
    """
    Get database schema information for a tenant
    """
    try:
        from .tools.database_tools import DatabaseTools
        
        db_tools = DatabaseTools(tenant_id)
        schema = db_tools.get_schema_info()
        
        return schema
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    print(f"🚀 Product Recommendation Agent starting...")
    print(f"📊 LangSmith tracing: {'enabled' if config.langsmith_tracing else 'disabled'}")
    
    # Schedule periodic cleanup
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            cleanup_old_agents()
    
    asyncio.create_task(periodic_cleanup())


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown"""
    print("👋 Shutting down Product Recommendation Agent...")
    # Clean up agents
    agent_cache.clear()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)