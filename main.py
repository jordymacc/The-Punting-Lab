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

app = FastAPI(title="Horse Racing Overlay API v2.0", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cached_overlays = []
cached_races = []
cached_weather = {}
last_updated = None

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

@app.on_event("startup")
async def startup_event():
    init_db()
    await refresh_race_data()
    asyncio.create_task(background_refresh())

async def background_refresh():
    while True:
        await asyncio.sleep(600)
        await refresh_race_data()
        await manager.broadcast({"overlays": cached_overlays, "weather": cached_weather, "last_updated": last_updated})

async def refresh_race_data():
    global cached_overlays, cached_races, last_updated
    try:
        races = await get_race_fields()
        overlays = []
        race_list = []
        for race in races:
            horses = race.get("horses", [])
            weather = cached_weather.get(race.get("track", ""), None)
            results = process_race(horses, weather)
            for r in results:
                overlays.append({**r, "track": race["track"], "race_number": race["race_number"], "race_name": race.get("race_name", ""), "race_time": race["race_time"], "distance": race.get("distance", "")})
            race_list.append({"track": race["track"], "race_number": race["race_number"], "race_name": race.get("race_name", ""), "race_time": race["race_time"], "distance": race.get("distance", "")})
        cached_overlays = overlays
        cached_races = race_list
        last_updated = datetime.utcnow().isoformat()
        print(f"[Refresh] {len(cached_races)} races, {len(cached_overlays)} runners loaded")
    except Exception as e:
        print(f"[Refresh] Error: {e}")

@app.get("/")
async def root():
    return {"message": "🏇 Horse Racing Overlay API v2.0", "status": "live", "features": ["predictions", "strategies", "analytics"], "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "2.0.0"}

@app.get("/api/overlays")
async def get_overlays():
    return {"overlays": cached_overlays, "last_updated": last_updated}

@app.get("/api/races")
async def get_races():
    return {"races": cached_races}

@app.get("/api/status")
async def get_status():
    return {"status": "live", "races_loaded": len(cached_races), "runners_loaded": len(cached_overlays), "last_updated": last_updated}

@app.get("/api/weather")
async def get_weather():
    return {"weather": cached_weather}

@app.get("/api/results")
async def get_results(db: Session = Depends(get_db)):
    rows = db.query(RaceResult).order_by(RaceResult.entered_at.desc()).all()
    return {"results": [{"race_id": r.race_id, "track": r.track, "race_number": r.race_number, "race_date": r.race_date, "winner": r.winner, "second": r.second, "third": r.third, "model_top_pick": r.model_top_pick, "model_top_pick_won": r.model_top_pick_won, "model_top_pick_placed": r.model_top_pick_placed} for r in rows]}

@app.post("/api/results")
async def post_result(payload: dict, db: Session = Depends(get_db)):
    track = payload.get("track", "")
    race_number = payload.get("race_number", 0)
    winner = payload.get("winner", "")
    second = payload.get("second", "")
    third = payload.get("third", "")
    today = datetime.now().strftime("%Y-%m-%d")
    race_id = f"{track}_{race_number}_{today}"
    top_pick = next((o["horse_name"] for o in cached_overlays if o["track"] == track and o["race_number"] == race_number), None)
    won = bool(top_pick and top_pick.lower() == winner.lower())
    placed = bool(top_pick and top_pick.lower() in [winner.lower(), second.lower(), third.lower()])
    existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
    if existing:
        existing.winner = winner; existing.second = second; existing.third = third
        existing.model_top_pick = top_pick; existing.model_top_pick_won = won; existing.model_top_pick_placed = placed
    else:
        db.add(RaceResult(race_id=race_id, track=track, race_number=race_number, race_date=today, winner=winner, second=second, third=third, model_top_pick=top_pick, model_top_pick_won=won, model_top_pick_placed=placed))
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
    return {"total_races": total, "wins": wins, "places": places, "win_rate": round(wins/total*100,1), "place_rate": round(places/total*100,1)}

@app.post("/api/refresh")
async def manual_refresh():
    await refresh_race_data()
    return {"status": "refreshed", "races": len(cached_races), "runners": len(cached_overlays)}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({"overlays": cached_overlays, "weather": cached_weather, "last_updated": last_updated})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
