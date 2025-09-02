# LangGraph Chat Agent

This directory contains the LangGraph-based conversational AI agent that powers the e-commerce chat system.

## Architecture

The agent uses a **graph-based workflow** where user intents are classified and routed to specialized subgraphs.

## Core Components

### 🧠 Main Graph (`main_graph.py`)
- Entry point for all chat interactions
- Orchestrates the overall workflow
- Routes to appropriate subgraphs based on intent

### 🎯 Intent Classification (`classify_intent_node.py`)
- Analyzes user messages to determine intent
- Classifies into: product_recommendation, product_inquiry, store_brand, or unrelated
- Fetches conversation context and tenant information

### 📦 Subgraph Workflows

#### `product_recommendation_graph.py`
- Handles product search and recommendations
- Extracts filters from conversation
- Fetches and validates relevant products
- Returns structured ProductCard responses

#### `product_inquiry_graph.py`
- Answers specific product questions
- Provides detailed product information
- Handles availability and specification queries

#### `store_brand_graph.py`
- Responds to store-related questions
- Uses tenant brand voice and description
- Handles business hours, policies, etc.

#### `unrelated_graph.py`
- Politely redirects off-topic queries
- Maintains helpful, professional tone

### 🔧 Supporting Modules

#### `graph_state.py`
- Defines GraphState data structure
- Manages conversation state across nodes
- Includes intent decisions and product data

#### `config.py`
- LangSmith configuration
- Redis connection settings
- Model parameters

#### `error_node.py`
- Centralized error handling
- User-friendly error messages

#### `product_tools.py`
- Product search utilities
- SQL and semantic search integration
- Filter extraction from natural language

## Data Flow

1. User message → Intent Classification
2. Intent → Route to appropriate subgraph
3. Subgraph → Process and generate response
4. Response → Format and return to user

## Key Features

- **Multi-intent routing**: Different workflows for different user needs
- **Context awareness**: Uses conversation history for better responses
- **Tenant isolation**: Respects multi-tenant boundaries
- **Structured responses**: Returns typed ProductCard data for frontend
- **Error resilience**: Graceful error handling throughout