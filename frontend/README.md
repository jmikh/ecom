# Frontend Application

This directory contains all frontend code for the e-commerce chat system, including the embeddable widget, dashboard, and product catalog.

## Directory Structure

```
frontend/
├── public/              # Static HTML pages
│   ├── index.html      # Home page with product catalog
│   ├── dashboard.html  # Analytics dashboard
│   └── typed-example.html # TypeScript example
├── src/                # Source JavaScript/TypeScript
│   ├── widget.js       # Embeddable chat widget
│   ├── widget-typed.ts # TypeScript widget version
│   └── types/          # TypeScript definitions
│       └── types.ts    # Generated from Pydantic
├── dist/               # Built/compiled files
├── assets/             # Static assets
│   └── screenshots/    # UI screenshots
└── package.json        # Node.js dependencies

```

## Applications

### 🏠 Home Page (`public/index.html`)
**Full product catalog with integrated chat**
- Product grid with images and prices
- Search and filtering capabilities
- Sort by price, name
- Filter by type, price range, discount
- Responsive design
- Integrated chat widget

### 💬 Chat Widget (`src/widget.js`)
**Embeddable customer support chat**
- Self-contained (no external dependencies)
- Floating bubble interface
- Product card rendering
- Markdown support
- Session persistence
- Auto-reconnection
- Minimizable UI

Features:
- Real-time streaming responses
- Product recommendations with images
- Price display
- Loading states
- Error handling

### 📊 Analytics Dashboard (`public/dashboard.html`)
**Tenant management and analytics**
- Real-time metrics (KPIs)
- Editable tenant settings
- Interactive charts (Chart.js)
- Date range filtering
- Session history
- Cost tracking

Dashboard sections:
- Overview metrics
- Sessions over time
- Message volume
- Cost breakdown
- Hourly activity
- Top products
- Recent sessions

### 🔧 TypeScript Support
- Type definitions in `src/types/`
- Generated from backend Pydantic models
- Ensures frontend-backend contract
- Example implementation in `typed-example.html`

## Development

### Building TypeScript
```bash
cd frontend
npm install
npm run build
```

### Type Generation
```bash
# From project root
python generate_types.py
```

### Widget Integration
Embed the widget on any page:
```html
<script src="http://localhost:8000/src/widget.js" 
        data-tenant-id="YOUR_TENANT_ID">
</script>
```

### Dashboard Access
```
http://localhost:8000/static/dashboard.html?tenant_id=YOUR_TENANT_ID
```

## API Endpoints

The frontend communicates with these backend endpoints:
- `POST /api/session` - Create/validate session
- `POST /api/chat/stream` - Stream chat responses
- `GET /api/products/{tenant_id}` - Get product catalog
- `GET /api/dashboard/{tenant_id}/*` - Dashboard data

## Technologies

- **Vanilla JavaScript** - Widget for zero dependencies
- **TypeScript** - Type safety for complex interactions
- **Chart.js** - Data visualization (CDN)
- **Marked.js** - Markdown rendering (embedded)
- **Server-Sent Events** - Real-time streaming

## Deployment

Frontend files are served by FastAPI:
- `/static/*` → `frontend/public/`
- `/src/*` → `frontend/src/`

No build step required for JavaScript widget.
TypeScript compilation optional for type checking.