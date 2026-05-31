
fixed_main_py = '''import asyncio
import json
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import structlog
from config import config

# ── Database ──────────────────────────────────────────────────────
from database import (
    init_db, SessionLocal, Race, Horse, WeatherData, RaceResult, get_db
)

# ── Agents & Overlay Engine ─────────────────────────────────────
from agents import state as agent_state, start_all_agents, consensus
from overlay_model import process_race
from weather import get_all_track_weather
from scraper import get_race_fields

# ── Prediction / Strategy / Metrics ───────────────────────────────
from prediction_tracker import prediction_tracker, RacePrediction, HorsePrediction
from racing_metrics import racing_tracker
from betting_strategy import BettingStrategyEngine

# ── Monitoring ────────────────────────────────────────────────────
from monitoring import monitor, get_metrics_response, get_health_status

# ═════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═════════════════════════════════════════════════════════════════

app = FastAPI(
    title="The Punting Lab API",
    version="3.0.0",
    description="Horse racing overlay, predictions & betting strategy"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Strategy engine (lazy init)
strategy_engine = None

# WebSocket connections
active_connections: list[WebSocket] = []


# ═════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    global strategy_engine

    # Database
    init_db()

    # Structured logging
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    # Strategy engine
    strategy_engine = BettingStrategyEngine(prediction_tracker)

    # Start background agents (scraper, weather, overlays, etc.)
    asyncio.create_task(start_all_agents())

    print("=" * 60)
    print("🚀  THE PUNTING LAB API v3.0")
    print("=" * 60)


# ═════════════════════════════════════════════════════════════════
# ROOT & HEALTH
# ═════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "message": "🏇 The Punting Lab API v3.0",
        "status": "live",
        "features": [
            "overlays", "races", "weather", "results",
            "predictions", "strategies", "analytics", "ws"
        ],
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return get_health_status()


# ═════════════════════════════════════════════════════════════════
# CORE API — what the frontend actually calls
# ═════════════════════════════════════════════════════════════════

@app.get("/api/overlays")
async def get_overlays():
    """Return all overlay-ranked runners + AI consensus picks."""
    return {
        "overlays": agent_state.get("overlays", []),
        "ai_picks": agent_state.get("ai_picks", []),
        "last_updated": agent_state.get("last_updated"),
    }


@app.get("/api/races")
async def get_races():
    """Return raw race fields (with horses)."""
    return {"races": agent_state.get("races", [])}


@app.get("/api/weather")
async def get_weather():
    """Return latest track weather."""
    return {"weather": agent_state.get("weather", {})}


@app.get("/api/status")
async def get_status():
    """Quick system status for the frontend header."""
    return {
        "status": agent_state.get("status", "unknown"),
        "races_loaded": len(agent_state.get("races", [])),
        "overlays_loaded": len(agent_state.get("overlays", [])),
        "last_updated": agent_state.get("last_updated"),
    }


# ═════════════════════════════════════════════════════════════════
# RESULTS (single + bulk)
# ═════════════════════════════════════════════════════════════════

@app.get("/api/results")
async def get_results():
    """Return all entered race results."""
    db = SessionLocal()
    try:
        rows = db.query(RaceResult).order_by(RaceResult.entered_at.desc()).all()
        return {
            "results": [
                {
                    "race_id": r.race_id,
                    "track": r.track,
                    "race_number": r.race_number,
                    "race_date": r.race_date,
                    "winner": r.winner,
                    "second": r.second,
                    "third": r.third,
                    "model_top_pick": getattr(r, "model_top_pick", None),
                    "model_top_pick_won": getattr(r, "model_top_pick_won", False),
                    "model_top_pick_placed": getattr(r, "model_top_pick_placed", False),
                }
                for r in rows
            ]
        }
    finally:
        db.close()


@app.post("/api/results")
async def post_result(data: dict):
    """Save a single race result."""
    db = SessionLocal()
    try:
        race_id = f"{data['track']}_{data['race_number']}_{datetime.now().strftime('%Y-%m-%d')}"
        # Upsert
        existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
        if existing:
            existing.winner = data.get("winner", "")
            existing.second = data.get("second", "")
            existing.third = data.get("third", "")
            existing.entered_at = datetime.utcnow()
        else:
            db.add(RaceResult(
                race_id=race_id,
                track=data["track"],
                race_number=data["race_number"],
                race_date=datetime.now().strftime("%Y-%m-%d"),
                winner=data.get("winner", ""),
                second=data.get("second", ""),
                third=data.get("third", ""),
            ))
        db.commit()

        # Broadcast to WebSocket clients
        await broadcast({"type": "result_saved", "race_id": race_id})
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@app.post("/api/bulk-results")
async def post_bulk_results(data: dict):
    """Save multiple results at once (from bulk.html)."""
    db = SessionLocal()
    saved = 0
    skipped = 0
    try:
        for r in data.get("results", []):
            race_id = f"{r['track']}_{r['race_number']}_{r['race_date']}"
            if db.query(RaceResult).filter(RaceResult.race_id == race_id).first():
                skipped += 1
                continue
            db.add(RaceResult(
                race_id=race_id,
                track=r["track"],
                race_number=r["race_number"],
                race_date=r["race_date"],
                winner=r.get("winner", ""),
                second=r.get("second", ""),
                third=r.get("third", ""),
            ))
            saved += 1
        db.commit()
        return {"success": True, "saved": saved, "skipped": skipped}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════
# ACCURACY
# ═════════════════════════════════════════════════════════════════

@app.get("/api/accuracy")
async def get_accuracy():
    """Model accuracy vs entered results."""
    db = SessionLocal()
    try:
        results = db.query(RaceResult).all()
        if not results:
            return {"total": 0, "wins": 0, "places": 0, "win_rate": 0, "place_rate": 0}

        total = len(results)
        wins = sum(1 for r in results if r.model_top_pick_won)
        places = sum(1 for r in results if r.model_top_pick_placed)

        return {
            "total": total,
            "wins": wins,
            "places": places,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "place_rate": round(places / total * 100, 1) if total else 0,
        }
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════
# PREDICTIONS (advanced analytics)
# ═════════════════════════════════════════════════════════════════

@app.get("/predictions/accuracy")
async def get_prediction_accuracy():
    return prediction_tracker.get_overall_accuracy()


@app.get("/predictions/analysis")
async def get_prediction_analysis():
    return {
        "overall": prediction_tracker.get_overall_accuracy(),
        "by_conditions": prediction_tracker.get_accuracy_by_conditions(),
        "confidence_analysis": prediction_tracker.get_confidence_analysis(),
        "recent_trend": prediction_tracker.get_recent_performance_trend(days=14),
    }


@app.get("/predictions/performance/{days}")
async def get_recent_performance(days: int):
    return prediction_tracker.get_recent_performance_trend(days)


@app.post("/predictions/record")
async def record_prediction(race_data: dict):
    try:
        horses = [HorsePrediction(**h) for h in race_data.get("horses", [])]
        race_pred = RacePrediction(
            race_id=race_data["race_id"],
            track=race_data["track"],
            race_time=datetime.fromisoformat(race_data["race_time"]),
            race_type=race_data.get("race_type", "unknown"),
            distance=race_data.get("distance", 0),
            surface=race_data.get("surface", "unknown"),
            weather=race_data.get("weather", "unknown"),
            field_size=race_data.get("field_size", len(horses)),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data["predicted_winner"],
            predicted_quinella=race_data.get("predicted_quinella", []),
            predicted_trifecta=race_data.get("predicted_trifecta", []),
        )
        prediction_tracker.record_prediction(race_pred)
        return {"success": True, "race_id": race_data["race_id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/predictions/result")
async def record_race_result(result_data: dict):
    try:
        prediction_tracker.record_race_result(
            race_id=result_data["race_id"],
            results=result_data["results"],
        )
        return {"success": True, "race_id": result_data["race_id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════
# STRATEGY
# ═════════════════════════════════════════════════════════════════

@app.post("/strategy/analyze-race")
async def analyze_race_strategy(race_data: dict):
    try:
        horses = [HorsePrediction(**h) for h in race_data.get("horses", [])]
        race_pred = RacePrediction(
            race_id=race_data["race_id"],
            track=race_data["track"],
            race_time=datetime.fromisoformat(race_data["race_time"]),
            race_type=race_data.get("race_type", "unknown"),
            distance=race_data.get("distance", 0),
            surface=race_data.get("surface", "unknown"),
            weather=race_data.get("weather", "unknown"),
            field_size=race_data.get("field_size", len(horses)),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data["predicted_winner"],
            predicted_quinella=race_data.get("predicted_quinella", []),
            predicted_trifecta=race_data.get("predicted_trifecta", []),
        )
        strategy = strategy_engine.analyze_race_strategy(race_pred)
        from dataclasses import asdict
        return asdict(strategy)
    except Exception as e:
        return {"error": str(e)}


@app.get("/strategy/bankroll-advice")
async def get_bankroll_advice():
    return strategy_engine.get_bankroll_management_advice()


@app.post("/strategy/set-bankroll")
async def set_bankroll(data: dict):
    try:
        amount = data.get("amount")
        if amount and amount > 0:
            strategy_engine.set_bankroll(amount)
            return {"success": True, "new_bankroll": amount}
        return {"error": "Invalid bankroll amount"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/strategy/performance-summary")
async def get_strategy_performance():
    overall = prediction_tracker.get_overall_accuracy()
    conditions = prediction_tracker.get_accuracy_by_conditions()
    return {
        "overall_performance": overall,
        "performance_by_conditions": conditions,
        "strategy_recommendations": {
            "conservative_situations": "When track accuracy < 20%",
            "aggressive_situations": "When track accuracy > 30% and ROI > 5%",
            "value_hunting_situations": "When overlays > 30% regardless of accuracy",
        },
    }


# ═════════════════════════════════════════════════════════════════
# RACING METRICS
# ═════════════════════════════════════════════════════════════════

@app.get("/metrics/racing")
async def racing_metrics():
    return racing_tracker.get_performance_summary()


@app.get("/metrics/racing/sources")
async def scraping_source_health():
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
            "status": status,
            "success_rate": success_rate,
            "freshness_seconds": freshness,
            "average_response_time": metrics.average_response_time,
            "data_quality": metrics.data_quality_score,
        }
    return sources


# ═════════════════════════════════════════════════════════════════
# WEBSOCKET — real-time broadcast
# ═════════════════════════════════════════════════════════════════

async def broadcast(message: dict):
    """Send JSON to all connected WebSocket clients."""
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    racing_tracker.track_websocket_connection(True)

    # Send current state immediately
    await websocket.send_json({
        "type": "init",
        "races_loaded": len(agent_state.get("races", [])),
        "overlays_loaded": len(agent_state.get("overlays", [])),
        "status": agent_state.get("status", "unknown"),
    })

    try:
        while True:
            msg = await websocket.receive_text()
            # Echo or handle commands
            if msg == "ping":
                await websocket.send_text("pong")
            else:
                await websocket.send_json({"type": "echo", "message": msg})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        racing_tracker.track_websocket_connection(False)


# ═════════════════════════════════════════════════════════════════
# DASHBOARDS (HTML pages served from same backend)
# ═════════════════════════════════════════════════════════════════

@app.get("/dashboard/strategy", response_class=HTMLResponse)
async def strategy_dashboard():
    try:
        with open("strategy_dashboard.html", "r") as f:
            html = f.read()
            return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("<h1>Strategy Dashboard</h1><p>File not found</p>")


@app.get("/dashboard/predictions", response_class=HTMLResponse)
async def prediction_dashboard():
    try:
        with open("prediction_dashboard.html", "r") as f:
            html = f.read()
            return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("<h1>Prediction Dashboard</h1><p>File not found</p>")


@app.get("/dashboard/monitoring", response_class=HTMLResponse)
async def monitoring_dashboard():
    try:
        with open("monitoring_dashboard.html", "r") as f:
            html = f.read()
            return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("<h1>Monitoring Dashboard</h1><p>File not found</p>")


# ═════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═════════════════════════════════════════════════════════════════

@app.get("/metrics")
async def prometheus_metrics():
    return get_metrics_response()


# ═════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
    )
'''

with open('/mnt/agents/output/main.py', 'w') as f:
    f.write(fixed_main_py)

print("✅ Fixed main.py written to /mnt/agents/output/main.py")
print(f"📄 File size: {len(fixed_main_py)} chars, {len(fixed_main_py.splitlines())} lines")
