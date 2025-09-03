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
  
- **ChatServerResponse**: Generic structured chat response
  - `first_message` (optional): Introductory text before products (e.g., "Here are some products you might like:")
  - `products` (optional): List of ProductCards to display
  - `last_message` (optional): Follow-up text after products (e.g., "Is there anything else I can help you with?")
  - All fields are optional, allowing flexible response combinations

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

# Create a chat response with products
response = ChatServerResponse(
    first_message="Based on your search for bags, here are some options:",
    products=[card],
    last_message="These are eco-friendly and durable. Can I help you find anything else?"
)

# Or without products
response = ChatServerResponse(
    first_message="I couldn't find any products matching your criteria."
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