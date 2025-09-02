# Shared Components

This directory contains shared data models and utilities used across the application.

## Components

### 📋 `schemas.py`
**Pydantic models for product data**

Core data models that ensure type safety and validation across the system:

- **ProductCard**: Frontend display model
  - Product ID, name, vendor
  - Image URL
  - Price range (min/max)
  - Discount status
  
- **ProductRecommendationResponse**: Structured chat response
  - List of ProductCards
  - Explanation message
  - Used for type-safe frontend communication

- **ValidationResponse**: Product validation result
  - Selected products
  - Reasoning for selections
  - Handles product filtering logic

## Purpose

These shared schemas serve as:
- **Contract between backend and frontend**
- **Type safety for product data**
- **Consistent data structure across services**
- **Input/output validation**

## Usage

```python
from src.shared.schemas import ProductCard, ProductRecommendationResponse

# Create a product card
card = ProductCard(
    id=1,
    name="Canvas Bag",
    vendor="United By Blue",
    image_url="https://...",
    price_min=32.0,
    price_max=32.0,
    has_discount=False
)

# Create a recommendation response
response = ProductRecommendationResponse(
    products=[card],
    message="Here's a great canvas bag for you!"
)
```

## TypeScript Generation

These models are also used to generate TypeScript interfaces:
- Included in `all_models.py` for type generation
- Run `python generate_types.py` to update TypeScript definitions
- Ensures frontend-backend type consistency

## Integration Points

Used by:
- `src/agent/`: Product recommendation workflows
- `server/`: API response models
- `server/static/`: Frontend TypeScript interfaces