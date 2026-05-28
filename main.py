import uvicorn
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="Horse Racing Overlay API v2.0", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "🏇 Horse Racing Overlay API v2.0", 
        "status": "live",
        "features": ["predictions", "strategies", "analytics"],
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/dashboard/strategy")
async def strategy_dashboard():
    """Simple strategy dashboard."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Strategy Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .card { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🎯 AI Betting Strategy Dashboard</h1>
        <div class="card">
            <h2>Status</h2>
            <p>✅ API is working!</p>
            <p>🔧 Full strategy engine loading...</p>
        </div>
        <div class="card">
            <h2>Available Endpoints</h2>
            <ul>
                <li><a href="/docs">API Documentation</a></li>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/">API Status</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run("main_simple:app", host="0.0.0.0", port=8000, reload=False)
