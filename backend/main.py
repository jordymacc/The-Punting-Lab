import asyncio
import json
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import structlog
from config import config

from database import init_db, SessionLocal, Race, Horse, WeatherData, RaceResult, get_db
from agents import state as agent_state, start_all_agents, consensus
from overlay_model import process_race
from weather import get_all_track_weather
from scraper import get_race_fields

try:
    from racing_com_scraper import racing_com_scraper
    RACING_COM_AVAILABLE = True
except ImportError:
    RACING_COM_AVAILABLE = False
    racing_com_scraper = None

app = FastAPI(title="The Punting Lab API", version="3.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
active_connections = []

@app.on_event("startup")
async def startup_event():
    try: init_db()
    except Exception as e: print(f"DB init warning: {e}")
    try:
        structlog.configure(processors=[structlog.processors.JSONRenderer()], logger_factory=structlog.stdlib.LoggerFactory())
    except Exception as e: print(f"Logging warning: {e}")
    try: asyncio.create_task(start_all_agents())
    except Exception as e: print(f"Agents warning: {e}")
    if RACING_COM_AVAILABLE:
        try:
            from racing_com_agent import racing_com_odds_agent
            asyncio.create_task(racing_com_odds_agent())
            print("[Startup] Racing.com odds agent started")
        except Exception as e: print(f"Racing.com agent warning: {e}")
    print("=" * 60)
    print("THE PUNTING LAB API v3.3 (with Racing.com Live Odds)")
    print("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    if RACING_COM_AVAILABLE and racing_com_scraper:
        await racing_com_scraper.close()

@app.get("/")
async def root():
    return {"message": "The Punting Lab API v3.3", "status": "live", "features": ["overlays", "races", "weather", "results", "ws", "racing-com-odds"], "docs": "/docs", "racing_com_available": RACING_COM_AVAILABLE}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/overlays")
async def get_overlays():
    overlays = agent_state.get("overlays", [])
    if RACING_COM_AVAILABLE and racing_com_scraper and racing_com_scraper.odds_cache:
        overlays = racing_com_scraper.merge_with_overlays(overlays)
    return {"overlays": overlays, "ai_picks": agent_state.get("ai_picks", []), "last_updated": agent_state.get("last_updated"), "live_odds_available": RACING_COM_AVAILABLE and racing_com_scraper and racing_com_scraper.last_update is not None}

@app.get("/api/races")
async def get_races():
    return {"races": agent_state.get("races", [])}

@app.get("/api/weather")
async def get_weather():
    return {"weather": agent_state.get("weather", {})}

@app.get("/api/status")
async def get_status():
    return {"status": agent_state.get("status", "unknown"), "races_loaded": len(agent_state.get("races", [])), "overlays_loaded": len(agent_state.get("overlays", [])), "last_updated": agent_state.get("last_updated"), "live_odds_available": RACING_COM_AVAILABLE and racing_com_scraper and racing_com_scraper.last_update is not None}

@app.get("/api/accuracy")
async def get_accuracy():
    return {"accuracy": {"overall": 0, "top_rated": 0, "value_bets": 0, "total_predictions": 0, "winners_found": 0}, "by_rating": {}, "by_track_condition": {}, "message": "Accuracy tracking not yet implemented"}

@app.get("/api/racing-com/meetings")
async def get_racing_com_meetings():
    if not RACING_COM_AVAILABLE: return {"error": "Racing.com scraper not available", "meetings": []}
    meetings = await racing_com_scraper.scrape_meetings()
    return {"meetings": meetings, "count": len(meetings)}

@app.get("/api/racing-com/race-odds")
async def get_racing_com_race_odds(url: str):
    if not RACING_COM_AVAILABLE: return {"error": "Racing.com scraper not available"}
    odds = await racing_com_scraper.scrape_race_odds(url)
    return odds

@app.get("/api/racing-com/all-odds")
async def get_racing_com_all_odds():
    if not RACING_COM_AVAILABLE: return {"error": "Racing.com scraper not available"}
    all_odds = await racing_com_scraper.scrape_all_odds()
    return {"odds": all_odds, "race_count": len(all_odds), "last_update": racing_com_scraper.last_update.isoformat() if racing_com_scraper.last_update else None}

@app.get("/api/racing-com/merged-overlays")
async def get_racing_com_merged_overlays():
    overlays = agent_state.get("overlays", [])
    if not RACING_COM_AVAILABLE: return {"error": "Racing.com scraper not available", "overlays": overlays}
    if not racing_com_scraper.odds_cache or (racing_com_scraper.last_update and (datetime.now() - racing_com_scraper.last_update).seconds > 300):
        await racing_com_scraper.scrape_all_odds()
    merged = racing_com_scraper.merge_with_overlays(overlays)
    return {"overlays": merged, "ai_picks": agent_state.get("ai_picks", []), "last_updated": agent_state.get("last_updated"), "odds_last_update": racing_com_scraper.last_update.isoformat() if racing_com_scraper.last_update else None}

@app.get("/api/results")
async def get_results():
    db = SessionLocal()
    try:
        rows = db.query(RaceResult).order_by(RaceResult.entered_at.desc()).all()
        return {"results": [{"race_id": r.race_id, "track": r.track, "race_number": r.race_number, "race_date": r.race_date, "winner": r.winner, "second": r.second, "third": r.third} for r in rows]}
    finally:
        db.close()

@app.post("/api/results")
async def post_result(data: dict):
    db = SessionLocal()
    try:
        race_id = f"{data['track']}_{data['race_number']}_{datetime.now().strftime('%Y-%m-%d')}"
        existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
        if existing:
            existing.winner = data.get("winner", "")
            existing.second = data.get("second", "")
            existing.third = data.get("third", "")
            existing.entered_at = datetime.utcnow()
        else:
            db.add(RaceResult(race_id=race_id, track=data["track"], race_number=data["race_number"], race_date=datetime.now().strftime("%Y-%m-%d"), winner=data.get("winner", ""), second=data.get("second", ""), third=data.get("third", "")))
        db.commit()
        await broadcast({"type": "result_saved", "race_id": race_id})
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.post("/api/bulk-results")
async def post_bulk_results(data: dict):
    db = SessionLocal()
    saved = 0
    skipped = 0
    try:
        for r in data.get("results", []):
            race_id = f"{r['track']}_{r['race_number']}_{r['race_date']}"
            if db.query(RaceResult).filter(RaceResult.race_id == race_id).first():
                skipped += 1
                continue
            db.add(RaceResult(race_id=race_id, track=r["track"], race_number=r["race_number"], race_date=r["race_date"], winner=r.get("winner", ""), second=r.get("second", ""), third=r.get("third", "")))
            saved += 1
        db.commit()
        return {"success": True, "saved": saved, "skipped": skipped}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

async def broadcast(message: dict):
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
    await websocket.send_json({"type": "init", "races_loaded": len(agent_state.get("races", [])), "overlays_loaded": len(agent_state.get("overlays", [])), "status": agent_state.get("status", "unknown"), "live_odds_available": RACING_COM_AVAILABLE and racing_com_scraper and racing_com_scraper.last_update is not None})
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
            else:
                await websocket.send_json({"type": "echo", "message": msg})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.get("/dashboard/strategy", response_class=HTMLResponse)
async def strategy_dashboard():
    try:
        with open("strategy_dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Strategy Dashboard</h1><p>File not found</p>")

@app.get("/dashboard/predictions", response_class=HTMLResponse)
async def prediction_dashboard():
    try:
        with open("prediction_dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Prediction Dashboard</h1><p>File not found</p>")

@app.get("/dashboard/monitoring", response_class=HTMLResponse)
async def monitoring_dashboard():
    try:
        with open("monitoring_dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Monitoring Dashboard</h1><p>File not found</p>")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.RELOAD)
