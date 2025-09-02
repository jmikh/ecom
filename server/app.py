"""
FastAPI application for the chat server
"""

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from server.config import server_config
from server.models import ChatRequest, ChatResponse, SessionRequest, SessionResponse, ErrorResponse
from server.auth import TenantAuth, verify_rate_limit
from server.chat_service import web_chat_service
from server.dashboard.routes import router as dashboard_router
from src.database import get_database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting chat server...")
    db = get_database()
    yield
    # Shutdown
    logger.info("Shutting down chat server...")
    db.close()


# Create FastAPI app
app = FastAPI(
    title="E-commerce Chat API",
    description="Chat API for product recommendations",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.ALLOWED_ORIGINS,
    allow_credentials=server_config.ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id"]
)

# Mount frontend files
import os
# Serve frontend public files
frontend_public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public")
if not os.path.exists(frontend_public_dir):
    os.makedirs(frontend_public_dir)

# Serve frontend source files (for widget.js, etc.)
frontend_src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "src")

# Serve frontend dist files (compiled TypeScript)
frontend_dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

# Mount directories
app.mount("/static", StaticFiles(directory=frontend_public_dir), name="static")
app.mount("/src", StaticFiles(directory=frontend_src_dir), name="src")
app.mount("/dist", StaticFiles(directory=frontend_dist_dir), name="dist")

# Include dashboard routes
app.include_router(dashboard_router)


@app.get("/")
async def root():
    """Serve the home page"""
    from fastapi.responses import FileResponse
    import os
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "healthy", "service": "chat-api"}


@app.post("/api/session", response_model=SessionResponse)
async def create_or_get_session(
    request: SessionRequest
):
    """Create new session or validate existing one"""
    try:
        # Verify tenant exists
        tenant_info = TenantAuth.verify_tenant_in_db(request.tenant_id)
        
        # Get or create session
        session_id = web_chat_service.get_or_create_session(
            request.session_id, 
            request.tenant_id
        )
        
        # Calculate expiry
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(
            minutes=server_config.SESSION_TIMEOUT_MINUTES
        )
        
        return SessionResponse(
            session_id=session_id,
            tenant_id=request.tenant_id,
            created=(request.session_id != session_id),
            expires_at=expires_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Session management error")


@app.post("/api/chat", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    response: Response
):
    """Process chat message and return response"""
    try:
        # Verify tenant
        tenant_info = TenantAuth.verify_tenant_in_db(request.tenant_id)
        
        # Get or create session
        session_id = web_chat_service.get_or_create_session(
            request.session_id,
            request.tenant_id
        )
        
        # Set session cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=server_config.SESSION_TIMEOUT_MINUTES * 60,
            httponly=True,
            secure=True,
            samesite="none"
        )
        
        # Process message
        chat_response = await web_chat_service.process_message(
            request.message,
            session_id,
            request.tenant_id
        )
        
        return ChatResponse(
            session_id=session_id,
            response=chat_response
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat processing error")


@app.post("/api/chat/stream")
async def chat_message_stream(
    request: ChatRequest
):
    """Process chat message and stream response"""
    try:
        # Verify tenant
        tenant_info = TenantAuth.verify_tenant_in_db(request.tenant_id)
        
        # Get or create session
        session_id = web_chat_service.get_or_create_session(
            request.session_id,
            request.tenant_id
        )
        
        # Stream response
        return StreamingResponse(
            web_chat_service.process_message_stream(
                request.message,
                session_id,
                request.tenant_id
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": session_id
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        raise HTTPException(status_code=500, detail="Stream processing error")


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    tenant_id: str
):
    """Get chat history for a session"""
    try:
        # Verify tenant
        tenant_info = TenantAuth.verify_tenant_in_db(tenant_id)
        
        # Get history
        history = web_chat_service.get_conversation_history(session_id, tenant_id)
        
        return {"session_id": session_id, "messages": history}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        raise HTTPException(status_code=500, detail="History retrieval error")


@app.get("/api/products/{tenant_id}")
async def get_all_products(
    tenant_id: str,
    limit: int = 100,
    offset: int = 0
):
    """Get all products for a tenant"""
    try:
        # Verify tenant
        tenant_info = TenantAuth.verify_tenant_in_db(tenant_id)
        
        # Get database connection
        from src.database import get_database
        db = get_database()
        
        # Query products with images
        query = """
            SELECT 
                p.id, p.shopify_id, p.title, p.vendor, p.product_type,
                p.min_price, p.max_price, p.has_discount,
                p.handle, p.status,
                pi.src as image_url
            FROM products p
            LEFT JOIN LATERAL (
                SELECT src 
                FROM product_images 
                WHERE product_id = p.id 
                AND tenant_id = p.tenant_id
                ORDER BY position 
                LIMIT 1
            ) pi ON true
            WHERE p.tenant_id = %s
            ORDER BY p.updated_at DESC
            LIMIT %s OFFSET %s
        """
        
        results = db.run_read(query, (tenant_id, limit, offset), tenant_id=tenant_id)
        
        # Format products
        products = []
        for row in results:
            product = {
                "id": row["id"],
                "name": row["title"],
                "vendor": row["vendor"],
                "product_type": row["product_type"],
                "price_min": float(row["min_price"]) if row["min_price"] else 0,
                "price_max": float(row["max_price"]) if row["max_price"] else 0,
                "has_discount": row["has_discount"],
                "image_url": row["image_url"],
                "handle": row["handle"]
            }
            products.append(product)
        
        return {"products": products, "count": len(products)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Products fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred"
        ).model_dump()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host=server_config.API_HOST,
        port=server_config.API_PORT,
        reload=True,
        log_level="info"
    )