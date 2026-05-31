import asyncio
import json
import uvicorn
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import structlog
from config import config

# Import our new modules
from prediction_tracker import prediction_tracker, RacePrediction, HorsePrediction
from racing_metrics import racing_tracker
from betting_strategy import BettingStrategyEngine

app = FastAPI(title="Horse Racing Overlay API", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize strategy engine
strategy_engine = None

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global strategy_engine
    strategy_engine = BettingStrategyEngine(prediction_tracker)
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

# Basic endpoints
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
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

# Prediction endpoints
@app.get("/predictions/accuracy")
async def get_prediction_accuracy():
    """Get overall prediction accuracy metrics."""
    return prediction_tracker.get_overall_accuracy()

@app.get("/predictions/analysis")
async def get_prediction_analysis():
    """Get detailed prediction analysis."""
    return {
        'overall': prediction_tracker.get_overall_accuracy(),
        'by_conditions': prediction_tracker.get_accuracy_by_conditions(),
        'confidence_analysis': prediction_tracker.get_confidence_analysis(),
        'recent_trend': prediction_tracker.get_recent_performance_trend(days=14)
    }

@app.get("/predictions/performance/{days}")
async def get_recent_performance(days: int):
    """Get performance trend for specified number of days."""
    return prediction_tracker.get_recent_performance_trend(days)

@app.post("/predictions/record")
async def record_prediction(race_data: dict):
    """Record a new race prediction."""
    try:
        horses = [
            HorsePrediction(**horse) for horse in race_data.get('horses', [])
        ]
        
        race_pred = RacePrediction(
            race_id=race_data['race_id'],
            track=race_data['track'],
            race_time=datetime.fromisoformat(race_data['race_time']),
            race_type=race_data.get('race_type', 'unknown'),
            distance=race_data.get('distance', 0),
            surface=race_data.get('surface', 'unknown'),
            weather=race_data.get('weather', 'unknown'),
            field_size=race_data.get('field_size', len(horses)),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data['predicted_winner'],
            predicted_quinella=race_data.get('predicted_quinella', []),
            predicted_trifecta=race_data.get('predicted_trifecta', [])
        )
        
        prediction_tracker.record_prediction(race_pred)
        return {"success": True, "race_id": race_data['race_id']}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/predictions/result")
async def record_race_result(result_data: dict):
    """Record actual race results."""
    try:
        prediction_tracker.record_race_result(
            race_id=result_data['race_id'],
            results=result_data['results']
        )
        return {"success": True, "race_id": result_data['race_id']}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Strategy endpoints
@app.post("/strategy/analyze-race")
async def analyze_race_strategy(race_data: dict):
    """Get betting strategy for a specific race."""
    try:
        horses = [HorsePrediction(**horse) for horse in race_data.get('horses', [])]
        race_pred = RacePrediction(
            race_id=race_data['race_id'],
            track=race_data['track'],
            race_time=datetime.fromisoformat(race_data['race_time']),
            race_type=race_data.get('race_type', 'unknown'),
            distance=race_data.get('distance', 0),
            surface=race_data.get('surface', 'unknown'),
            weather=race_data.get('weather', 'unknown'),
            field_size=race_data.get('field_size', len(horses)),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data['predicted_winner'],
            predicted_quinella=race_data.get('predicted_quinella', []),
            predicted_trifecta=race_data.get('predicted_trifecta', [])
        )
        
        strategy = strategy_engine.analyze_race_strategy(race_pred)
        
        # Convert dataclass to dict for JSON response
        from dataclasses import asdict
        return asdict(strategy)
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/strategy/bankroll-advice")
async def get_bankroll_advice():
    """Get bankroll management advice."""
    return strategy_engine.get_bankroll_management_advice()

@app.post("/strategy/set-bankroll")
async def set_bankroll(data: dict):
    """Set current bankroll amount."""
    try:
        amount = data.get('amount')
        if amount and amount > 0:
            strategy_engine.set_bankroll(amount)
            return {"success": True, "new_bankroll": amount}
        else:
            return {"error": "Invalid bankroll amount"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/strategy/performance-summary")
async def get_strategy_performance():
    """Get performance summary for all strategies."""
    overall = prediction_tracker.get_overall_accuracy()
    conditions = prediction_tracker.get_accuracy_by_conditions()
    
    return {
        "overall_performance": overall,
        "performance_by_conditions": conditions,
        "strategy_recommendations": {
            "conservative_situations": "When track accuracy < 20%",
            "aggressive_situations": "When track accuracy > 30% and ROI > 5%",
            "value_hunting_situations": "When overlays > 30% regardless of accuracy"
        }
    }

# Racing metrics endpoints
@app.get("/metrics/racing")
async def racing_metrics():
    """Get racing-specific performance metrics."""
    return racing_tracker.get_performance_summary()

@app.get("/metrics/racing/sources")
async def scraping_source_health():
    """Get detailed scraping source health."""
    sources = {}
    for source, metrics in racing_tracker.scraping_metrics.items():
        freshness = racing_tracker.get_data_freshness(source)
        success_rate = racing_tracker.get_scraping_success_rate(source)
        
        status = "healthy"
        if success_rate < 0.8:
            status = "warning"
        if success_rate < 0.5 or (freshness and freshness > 300):
            status = "critical"
        
        sources[source] = {
            'status': status,
            'success_rate': success_rate,
            'freshness_seconds': freshness,
            'average_response_time': metrics.average_response_time,
            'data_quality': metrics.data_quality_score
        }
    
    return sources

# Dashboard endpoints
@app.get("/dashboard/strategy", response_class=HTMLResponse)
async def strategy_dashboard():
    """Serve the strategy dashboard."""
    try:
        with open('strategy_dashboard.html', 'r') as f:
            html = f.read()
            # Update API_BASE to point to current deployment
            html = html.replace('https://punting-lab-backend.onrender.com', f'https://{config.HOST}')
            return html
    except:
        return "<h1>Strategy Dashboard</h1><p>Dashboard file not found</p>"

@app.get("/dashboard/predictions", response_class=HTMLResponse)
async def prediction_dashboard():
    """Serve the prediction dashboard."""
    try:
        with open('prediction_dashboard.html', 'r') as f:
            html = f.read()
            html = html.replace('https://punting-lab-backend.onrender.com', f'https://{config.HOST}')
            return html
    except:
        return "<h1>Prediction Dashboard</h1><p>Dashboard file not found</p>"

# WebSocket for real-time updates
active_connections = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    racing_tracker.track_websocket_connection(True)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now - you can add real functionality here
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        racing_tracker.track_websocket_connection(False)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
    )