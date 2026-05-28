"""
Standalone Strategy Server
Run this alongside your existing overlay system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime
import httpx
import uvicorn

app = FastAPI(title="AI Betting Strategy Engine", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your live overlay API
OVERLAY_API = "https://punting-lab-backend.onrender.com"

@app.get("/")
async def root():
    return {
        "message": "🎯 AI Betting Strategy Engine",
        "status": "online",
        "overlay_api": OVERLAY_API,
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Interactive strategy dashboard."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎯 AI Strategy Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .btn {{ padding: 10px 20px; background: #2196f3; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; }}
            .btn:hover {{ background: #1976d2; }}
            .overlay-item {{ padding: 10px; margin: 5px 0; background: #e3f2fd; border-radius: 4px; }}
            .overlay-item.strong {{ background: #e8f5e8; border-left: 4px solid #4caf50; }}
            .overlay-item.good {{ background: #fff3e0; border-left: 4px solid #ff9800; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 AI Betting Strategy Dashboard</h1>
            
            <div class="card">
                <h2>✅ System Status</h2>
                <p><strong>Strategy Engine:</strong> Online</p>
                <p><strong>Overlay API:</strong> <a href="{OVERLAY_API}/api/overlays" target="_blank">Connected</a></p>
                <p><strong>Time:</strong> {now}</p>
            </div>
            
            <div class="card">
                <h2>📊 Today's Best Bets</h2>
                <button class="btn" onclick="loadOverlays()">🔄 Load Overlays</button>
                <div id="overlays-container" style="margin-top: 20px;">
                    <p>Click "Load Overlays" to fetch today's best value bets</p>
                </div>
            </div>
            
            <div class="card">
                <h2>💡 How It Works</h2>
                <p>This strategy engine analyzes overlay data from your racing system and identifies value bets where:</p>
                <ul>
                    <li><strong>Fair Value > Bookmaker Odds</strong> - We think the horse has better chances than the odds suggest</li>
                    <li><strong>Strong Track/Distance Form</strong> - Horse performs well in similar conditions</li>
                    <li><strong>Good Recent Form</strong> - Horse has been running well recently</li>
                </ul>
            </div>
            
            <div class="card">
                <h2>🔗 Quick Links</h2>
                <a href="{OVERLAY_API}" target="_blank" class="btn">🏇 Main Overlay Dashboard</a>
                <a href="{OVERLAY_API}/api/overlays" target="_blank" class="btn">📊 Overlay Data API</a>
                <a href="{OVERLAY_API}/docs" target="_blank" class="btn">📚 API Documentation</a>
            </div>
        </div>

        <script>
            async function loadOverlays() {{
                const container = document.getElementById('overlays-container');
                container.innerHTML = '<p>Loading overlays...</p>';
                
                try {{
                    const response = await fetch('{OVERLAY_API}/api/overlays');
                    const data = await response.json();
                    
                    if (data.overlays && data.overlays.length > 0) {{
                        const bestBets = data.overlays
                            .filter(h => h.fair_value > 15)
                            .sort((a, b) => b.fair_value - a.fair_value)
                            .slice(0, 10);
                        
                        let html = '<h3>Top 10 Value Bets:</h3>';
                        bestBets.forEach((horse, i) => {{
                            const rating = horse.fair_value > 20 ? 'strong' : 'good';
                            html += `
                                <div class="overlay-item ${{rating}}">
                                    <strong>#${{i+1}}: ${{horse.horse_name}}</strong> 
                                    (${{horse.track}} R${{horse.race_number}}, ${{horse.race_time}})<br>
                                    <strong>Fair Value:</strong> ${{horse.fair_value.toFixed(1)}}% | 
                                    <strong>Est Odds:</strong> ${{horse.est_fair_odds.toFixed(2)}} |
                                    <strong>Career Wins:</strong> ${{horse.career_wins}} |
                                    <strong>Track Wins:</strong> ${{horse.track_wins}}
                                </div>
                            `;
                        }});
                        container.innerHTML = html;
                    }} else {{
                        container.innerHTML = '<p>No overlays found</p>';
                    }}
                }} catch (error) {{
                    container.innerHTML = '<p style="color: red;">Error loading overlays: ' + error.message + '</p>';
                }}
            }}
        </script>
    </body>
    </html>
    '''
    return HTMLResponse(content=html)

@app.get("/api/recommendations")
async def get_recommendations():
    """Get betting recommendations based on overlay data."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{OVERLAY_API}/api/overlays", timeout=10.0)
            data = response.json()
            
            overlays = data.get('overlays', [])
            
            value_bets = [
                h for h in overlays 
                if h.get('fair_value', 0) > 15
            ]
            
            value_bets.sort(key=lambda x: x.get('fair_value', 0), reverse=True)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "total_overlays": len(overlays),
                "value_bets": len(value_bets),
                "top_recommendations": value_bets[:10],
                "strategy_notes": [
                    "Focus on horses with fair_value > 20%",
                    "Consider track and distance form",
                    "Use Kelly Criterion for bet sizing",
                    "Track your results for continuous improvement"
                ]
            }
            
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Could not fetch overlay data: {str(e)}")

@app.get("/api/bankroll")
async def get_bankroll():
    """Get bankroll management advice."""
    return {
        "recommended_unit_size": "1-2% of bankroll per bet",
        "daily_limit": "5% of bankroll",
        "max_concurrent_bets": 3,
        "strategy": "Focus on quality over quantity - only bet when fair_value > 20%"
    }

if __name__ == "__main__":
    print("🚀 Starting AI Strategy Server...")
    print(f"📊 Connecting to overlay API: {OVERLAY_API}")
    print("🌐 Dashboard: http://localhost:8001/dashboard")
    print("📚 API Docs: http://localhost:8001/docs")
    uvicorn.run("strategy_server:app", host="0.0.0.0", port=8001, reload=False)
