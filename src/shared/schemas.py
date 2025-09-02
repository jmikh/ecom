"""
Shared Pydantic schemas for structured responses
These models serve as the single source of truth for both backend and frontend
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ProductCard(BaseModel):
    """Single product card with all display information"""
    id: int = Field(description="Product ID from database")
    name: str = Field(description="Product name/title")
    vendor: str = Field(description="Brand or vendor name")
    image_url: Optional[str] = Field(None, description="Primary product image URL")
    price_min: float = Field(description="Minimum price")
    price_max: float = Field(description="Maximum price")
    has_discount: bool = Field(default=False, description="Whether product is on sale")
    
    class Config:
        # Allow the model to be used with ORM objects
        from_attributes = True


class ProductRecommendationResponse(BaseModel):
    """Response containing product cards and reasoning"""
    products: List[ProductCard] = Field(
        description="List of recommended products",
        default_factory=list
    )
    message: str = Field(
        description="LLM reasoning for these recommendations"
    )
    
    class Config:
        # Allow the model to be used with ORM objects
        from_attributes = True