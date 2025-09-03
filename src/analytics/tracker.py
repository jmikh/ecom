"""
Analytics tracking with LangChain callbacks
Tracks LLM usage, costs, and product events
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import asyncio

from langchain.callbacks.base import AsyncCallbackHandler, BaseCallbackHandler
from langchain.schema import LLMResult, BaseMessage

from src.database import get_database
from src.database.message_store import SessionManager


class AnalyticsCallbackHandler(AsyncCallbackHandler):
    """
    Track LLM usage and costs using actual API response data
    """
    
    # Pricing per 1M tokens - using base model names
    # The matching logic will use prefix matching
    PRICING = {
        # Custom/internal models
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        
        # Embedding models
        "text-embedding-3-small": {"input": 0.02, "output": 0},
        "text-embedding-3-large": {"input": 0.13, "output": 0},
        "text-embedding-ada-002": {"input": 0.10, "output": 0},
    }
    
    def __init__(self, tenant_id: str, session_id: str):
        """
        Initialize the analytics handler
        
        Args:
            tenant_id: Tenant UUID for tracking
            session_id: Session ID for grouping metrics
        """
        super().__init__()
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.db = get_database()
        self.session_manager = SessionManager()
        
        # Track cumulative metrics for the session
        self.total_tokens = 0
        self.total_cost = 0.0
        self.llm_calls = 0
    
    def _calculate_cost(
        self, 
        model_name: str, 
        prompt_tokens: int, 
        completion_tokens: int
    ) -> float:
        """
        Calculate cost based on model and token usage using prefix matching
        
        Args:
            model_name: Name of the model used
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Normalize model name for matching
        model_lower = model_name.lower()
        pricing = None
        
        # Use prefix matching - check if model name starts with any pricing key
        # Ordered by specificity (longer prefixes first)
        pricing_keys = sorted(self.PRICING.keys(), key=len, reverse=True)
        
        for pricing_key in pricing_keys:
            if model_lower.startswith(pricing_key):
                pricing = self.PRICING[pricing_key]
                break
        
        # Log error and default to zero cost if model not found
        if not pricing:
            print(f"❌ ERROR: No pricing found for model '{model_name}' - defaulting to zero cost")
            print(f"   Available pricing prefixes: {', '.join(sorted(self.PRICING.keys()))}")
            return 0.0
        
        # Calculate cost (pricing is per 1M tokens)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return total_cost
    
    async def on_llm_end(
        self,
        response: LLMResult,
        **kwargs
    ) -> None:
        """
        Called when LLM finishes generating
        
        Args:
            response: The LLM response containing usage data
        """
        try:
            # Extract token usage from response
            if response.llm_output and "token_usage" in response.llm_output:
                usage = response.llm_output["token_usage"]
                model_name = response.llm_output.get("model_name", "unknown")
                
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                
                # Calculate cost
                cost = self._calculate_cost(model_name, prompt_tokens, completion_tokens)
                
                # Update cumulative metrics
                self.total_tokens += total_tokens
                self.total_cost += cost
                self.llm_calls += 1
                
                # Log LLM usage
                print(f"📊 LLM Usage: {model_name} - {total_tokens} tokens, ${cost:.6f}")
                
                # Update session metrics in database with input/output tokens
                self.session_manager.update_session_metrics(
                    tenant_id=self.tenant_id,
                    session_id=self.session_id,
                    tokens_used=total_tokens,
                    cost=cost,
                    llm_calls=1,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens
                )
                
        except Exception as e:
            print(f"❌ Error tracking LLM usage: {e}")
    
    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Called when a chain finishes
        Can be used to track high-level metrics
        """
        # Log total session metrics
        if self.llm_calls > 0:
            print(f"📈 Session totals: {self.llm_calls} calls, {self.total_tokens} tokens, ${self.total_cost:.4f}")


class ProductAnalyticsTracker:
    """
    Track product-related events for analytics
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize product analytics tracker
        
        Args:
            tenant_id: Tenant UUID
        """
        self.tenant_id = tenant_id
        self.db = get_database()
    
    def track_product_event(
        self,
        product_id: int,
        event_type: str,
        session_id: Optional[str] = None
    ):
        """
        Track a product event
        
        Args:
            product_id: Product ID from database
            event_type: Type of event ('recommended', 'inquired', 'clicked')
            session_id: Optional session ID for context
        """
        query = """
            INSERT INTO product_analytics (
                tenant_id, product_id, event_type, session_id, created_at
            ) VALUES (%s, %s, %s, %s, NOW())
        """
        
        try:
            self.db.run_write(
                query,
                (self.tenant_id, product_id, event_type, session_id),
                tenant_id=self.tenant_id
            )
        except Exception as e:
            print(f"❌ Error tracking product event: {e}")
    
    def track_recommendations(
        self,
        product_ids: List[int],
        session_id: Optional[str] = None
    ):
        """
        Track multiple product recommendations
        
        Args:
            product_ids: List of recommended product IDs
            session_id: Optional session ID
        """
        for product_id in product_ids:
            self.track_product_event(product_id, "recommended", session_id)
    
    def track_inquiry(
        self,
        product_id: int,
        session_id: Optional[str] = None
    ):
        """
        Track a product inquiry
        
        Args:
            product_id: Product ID being inquired about
            session_id: Optional session ID
        """
        self.track_product_event(product_id, "inquired", session_id)
    
    def get_top_products(
        self,
        event_type: str = "recommended",
        limit: int = 10,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get top products by event type
        
        Args:
            event_type: Type of event to filter by
            limit: Number of products to return
            days: Time window in days
            
        Returns:
            List of products with event counts
        """
        query = """
            SELECT 
                p.id,
                p.title as name,
                p.vendor,
                p.min_price,
                p.max_price,
                COUNT(pa.id) as event_count
            FROM product_analytics pa
            JOIN products p ON pa.product_id = p.id
            WHERE pa.tenant_id = %s
            AND pa.event_type = %s
            AND pa.created_at > NOW() - INTERVAL '%s days'
            GROUP BY p.id, p.title, p.vendor, p.min_price, p.max_price
            ORDER BY event_count DESC
            LIMIT %s
        """
        
        results = self.db.run_read(
            query,
            (self.tenant_id, event_type, days, limit),
            tenant_id=self.tenant_id
        )
        
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "vendor": row["vendor"],
                "price_min": float(row["min_price"]) if row["min_price"] else 0,
                "price_max": float(row["max_price"]) if row["max_price"] else 0,
                "event_count": row["event_count"]
            }
            for row in results
        ] if results else []