#!/usr/bin/env python3
"""
Start the chat web server
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from server.config import server_config
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║         🚀 E-commerce Chat Server Starting...            ║
    ╚══════════════════════════════════════════════════════════╝
    
    📍 API Server: http://{server_config.API_HOST}:{server_config.API_PORT}
    📄 Dashboard:  http://{server_config.API_HOST}:{server_config.API_PORT}/static/dashboard.html
    📚 API Docs:   http://{server_config.API_HOST}:{server_config.API_PORT}/docs
    
    🔧 Widget Embed Code:
    <script src="http://{server_config.API_HOST}:{server_config.API_PORT}/src/widget.js" 
            data-tenant-id="6b028cbb-512d-4538-a3b1-71bc40f49ed1">
    </script>
    
    Press CTRL+C to stop the server
    """)
    
    uvicorn.run(
        "server.app:app",
        host=server_config.API_HOST,
        port=server_config.API_PORT,
        reload=True,
        log_level="info"
    )