"""
Shared Pydantic schemas for structured responses
These models serve as the single source of truth for both backend and frontend
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ProductCard(BaseModel):
    """Single product card with all display information"""
    id: int = Field(description="Product ID from database")
    shopify_id: Optional[str] = Field(None, description="Shopify product ID")
    name: str = Field(description="Product name/title")
    vendor: str = Field(description="Brand or vendor name")
    image_url: Optional[str] = Field(None, description="Primary product image URL")
    price_min: float = Field(description="Minimum price")
    price_max: float = Field(description="Maximum price")
    has_discount: bool = Field(default=False, description="Whether product is on sale")
    
    class Config:
        # Allow the model to be used with ORM objects
        from_attributes = True


class ChatServerResponse(BaseModel):
    """Generic chat server response that can contain text and/or products"""
    message: Optional[str] = Field(
        None,
        description="Message to display to the user"
    )
    products: Optional[List[ProductCard]] = Field(
        None,
        description="List of product cards to display"
    )
    
    class Config:
        # Allow the model to be used with ORM objects
        from_attributes = True