import uvicorn
import asyncio
from datetime import datetime
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List

from database import init_db, get_db, Race, Horse, WeatherData, RaceResult
from overlay_model import process_race
from scraper import get_race_fields
try:
    from racing_com_scraper import scrape_live_odds, inject_odds
except Exception as e:
    print(f"[Odds] Import failed: {e}")
    async def scrape_live_odds(*a, **kw): return {}
    def inject_odds(r, o): return r
app = FastAPI(title="Horse Racing Overlay API v2.0", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory cache ──────────────────────────────────────────────────────────
cached_overlays = []
cached_races = []
cached_weather = {}
last_updated = None

# ── WebSocket connection manager ─────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)

manager = ConnectionManager()

# ── Startup: init DB and load race data ──────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    import subprocess, sys
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                      check=True, timeout=120)
        print("[Startup] Chromium installed")
    except Exception as e:
        print(f"[Startup] Chromium install failed: {e}")
    init_db()
    asyncio.create_task(background_refresh_delayed())
    asyncio.create_task(run_initial_refresh())

async def run_initial_refresh():
    await asyncio.sleep(2)
    await refresh_race_data()

async def background_refresh_delayed():
    await asyncio.sleep(620)
    while True:
        await refresh_race_data()
        await manager.broadcast({"overlays": cached_overlays, "weather": cached_weather, "last_updated": last_updated})
        await asyncio.sleep(600)

async def refresh_race_data():
    global cached_overlays, cached_races, last_updated
    try:
        races = await get_race_fields()

        # ── inject live odds from Racing.com ──────────────────────────────
        try:
            odds_map = await scrape_live_odds("https://www.racing.com/todays-racing")
            if odds_map:
                races = inject_odds(races, odds_map)
        except Exception as oe:
            print(f"[Odds] Skipping live odds injection: {oe}")
        overlays = []
        race_list = []

        for race in races:
            horses = race.get("horses", [])
            weather = cached_weather.get(race.get("track", ""), None)
            results = process_race(horses, weather)

            for r in results:
                overlays.append({
                    **r,
                    "track": race["track"],
                    "race_number": race["race_number"],
                    "race_name": race.get("race_name", ""),
                    "race_time": race["race_time"],
                    "race_date": race.get("race_date", ""),
                    "distance": race.get("distance", ""),
                })

            race_list.append({
                "track": race["track"],
                "race_number": race["race_number"],
                "race_name": race.get("race_name", ""),
                "race_time": race["race_time"],
                "race_date": race.get("race_date", ""),
                "distance": race.get("distance", ""),
            })

        cached_overlays = overlays
        cached_races = race_list
        last_updated = datetime.utcnow().isoformat()
        print(f"[Refresh] {len(cached_races)} races, {len(cached_overlays)} runners loaded")
    except Exception as e:
        print(f"[Refresh] Error: {e}")

# ── Routes ────────────────────────────────────────────────────────────────────

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

@app.get("/api/overlays")
async def get_overlays():
    return {
        "overlays": cached_overlays,
        "last_updated": last_updated,
    }

@app.get("/api/races")
async def get_races():
    return {"races": cached_races}

@app.get("/api/status")
async def get_status():
    return {
        "status": "live",
        "races_loaded": len(cached_races),
        "runners_loaded": len(cached_overlays),
        "last_updated": last_updated,
    }

@app.get("/api/weather")
async def get_weather():
    return {"weather": cached_weather}

@app.get("/api/results")
async def get_results(db: Session = Depends(get_db)):
    rows = db.query(RaceResult).order_by(RaceResult.entered_at.desc()).all()
    results = []
    for r in rows:
        results.append({
            "race_id": r.race_id,
            "track": r.track,
            "race_number": r.race_number,
            "race_date": r.race_date,
            "winner": r.winner,
            "second": r.second,
            "third": r.third,
            "model_top_pick": r.model_top_pick,
            "model_top_pick_won": r.model_top_pick_won,
            "model_top_pick_placed": r.model_top_pick_placed,
        })
    return {"results": results}

@app.post("/api/results")
async def post_result(payload: dict, db: Session = Depends(get_db)):
    track = payload.get("track", "")
    race_number = payload.get("race_number", 0)
    winner = payload.get("winner", "")
    second = payload.get("second", "")
    third = payload.get("third", "")
    today = datetime.now().strftime("%Y-%m-%d")
    race_id = f"{track}_{race_number}_{today}"

    # Find model's top pick for this race from cached overlays
    top_pick = None
    for o in cached_overlays:
        if o["track"] == track and o["race_number"] == race_number:
            top_pick = o["horse_name"]
            break

    won = top_pick and top_pick.lower() == winner.lower() if top_pick else False
    placed = top_pick and top_pick.lower() in [winner.lower(), second.lower(), third.lower()] if top_pick else False

    existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
    if existing:
        existing.winner = winner
        existing.second = second
        existing.third = third
        existing.model_top_pick = top_pick
        existing.model_top_pick_won = won
        existing.model_top_pick_placed = placed
    else:
        db.add(RaceResult(
            race_id=race_id,
            track=track,
            race_number=race_number,
            race_date=today,
            winner=winner,
            second=second,
            third=third,
            model_top_pick=top_pick,
            model_top_pick_won=won,
            model_top_pick_placed=placed,
        ))
    db.commit()
    return {"status": "saved"}

@app.get("/api/accuracy")
async def get_accuracy(db: Session = Depends(get_db)):
    rows = db.query(RaceResult).all()
    total = len(rows)
    if total == 0:
        return {"total_races": 0, "wins": 0, "places": 0, "win_rate": 0, "place_rate": 0}
    wins = sum(1 for r in rows if r.model_top_pick_won)
    places = sum(1 for r in rows if r.model_top_pick_placed)
    return {
        "total_races": total,
        "wins": wins,
        "places": places,
        "win_rate": round(wins / total * 100, 1),
        "place_rate": round(places / total * 100, 1),
    }

@app.post("/api/refresh")
async def manual_refresh():
    await refresh_race_data()
    return {"status": "refreshed", "races": len(cached_races), "runners": len(cached_overlays)}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send current data immediately on connect
        await ws.send_json({
            "overlays": cached_overlays,
            "weather": cached_weather,
            "last_updated": last_updated,
        })
        while True:
            await ws.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(ws)

@app.get("/dashboard/strategy")
async def strategy_dashboard():
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
        </div>
        <div class="card">
            <h2>Available Endpoints</h2>
            <ul>
                <li><a href="/docs">API Documentation</a></li>
                <li><a href="/api/overlays">Overlays</a></li>
                <li><a href="/api/races">Races</a></li>
                <li><a href="/api/status">Status</a></li>
                <li><a href="/api/weather">Weather</a></li>
                <li><a href="/api/results">Results</a></li>
                <li><a href="/api/accuracy">Accuracy</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)