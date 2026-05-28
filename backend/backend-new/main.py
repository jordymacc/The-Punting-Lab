import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from database import init_db, SessionLocal, RaceResult
from agents import state, start_all_agents

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(start_all_agents())
    yield

app = FastAPI(title="Horse Racing Overlay", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).parent.parent / "frontend"

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(FRONTEND / "index.html")

@app.get("/style.css")
async def css():
    return FileResponse(FRONTEND / "style.css", media_type="text/css")

@app.get("/app.js")
async def js():
    return FileResponse(FRONTEND / "app.js", media_type="application/javascript")

@app.get("/bulk", response_class=HTMLResponse)
async def bulk_page():
    return FileResponse(FRONTEND / "bulk.html")

@app.get("/api/races")
async def get_races():
    return {"races": state["races"], "last_updated": state["last_updated"]}

@app.get("/api/overlays")
async def get_overlays():
    return {
        "overlays": state["overlays"],
        "last_updated": state["last_updated"],
        "status": state["status"],
    }

@app.get("/api/weather")
async def get_weather():
    return {"weather": state["weather"]}

@app.get("/api/status")
async def get_status():
    return {
        "status": state["status"],
        "races_loaded": len(state["races"]),
        "overlays_found": len(state["overlays"]),
        "last_updated": state["last_updated"],
    }

# ---------- Results endpoints ----------
@app.post("/api/results")
async def save_result(payload: dict):
    try:
        db = SessionLocal()
        track       = payload.get("track", "")
        race_number = payload.get("race_number", 0)
        winner      = payload.get("winner", "")
        second      = payload.get("second", "")
        third       = payload.get("third", "")
        race_date   = datetime.now().strftime("%Y-%m-%d")
        race_id     = f"{track}_{race_number}_{race_date}"

        # Find model's top pick for this race from current state
        model_top_pick = ""
        model_top_pick_won = False
        model_top_pick_placed = False

        for o in state["overlays"]:
            if o.get("track") == track and o.get("race_number") == race_number:
                model_top_pick = o.get("horse_name", "")
                break

        if model_top_pick and winner:
            model_top_pick_won = model_top_pick.lower() == winner.lower()
            model_top_pick_placed = model_top_pick.lower() in [
                winner.lower(),
                second.lower(),
                third.lower()
            ]

        # Upsert — update if exists
        existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
        if existing:
            existing.winner = winner
            existing.second = second
            existing.third = third
            existing.model_top_pick = model_top_pick
            existing.model_top_pick_won = model_top_pick_won
            existing.model_top_pick_placed = model_top_pick_placed
            existing.entered_at = datetime.utcnow()
        else:
            db.add(RaceResult(
                race_id=race_id,
                track=track,
                race_number=race_number,
                race_date=race_date,
                winner=winner,
                second=second,
                third=third,
                model_top_pick=model_top_pick,
                model_top_pick_won=model_top_pick_won,
                model_top_pick_placed=model_top_pick_placed,
            ))

        db.commit()
        db.close()
        return {
            "success": True,
            "model_top_pick": model_top_pick,
            "model_top_pick_won": model_top_pick_won,
            "model_top_pick_placed": model_top_pick_placed,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/results")
async def get_results():
    try:
        db = SessionLocal()
        results = db.query(RaceResult).order_by(RaceResult.entered_at.desc()).all()
        db.close()
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
                    "model_top_pick": r.model_top_pick,
                    "model_top_pick_won": r.model_top_pick_won,
                    "model_top_pick_placed": r.model_top_pick_placed,
                    "entered_at": r.entered_at.isoformat() if r.entered_at else None,
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"results": [], "error": str(e)}

@app.get("/api/accuracy")
async def get_accuracy():
    try:
        db = SessionLocal()
        results = db.query(RaceResult).all()
        db.close()
        total  = len(results)
        wins   = sum(1 for r in results if r.model_top_pick_won)
        places = sum(1 for r in results if r.model_top_pick_placed)
        return {
            "total_races": total,
            "wins": wins,
            "places": places,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "place_rate": round(places / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        return {"total_races": 0, "wins": 0, "places": 0, "win_rate": 0, "place_rate": 0}
# ---------- Historical backfill ----------
@app.post("/api/backfill-history")
async def backfill_history(days: int = 7):
    try:
        from scrape_historical import backfill_history as run_backfill
        stats = await run_backfill(days)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}
# ---------- WebSocket ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "init",
            "overlays": state["overlays"],
            "weather": state["weather"],
            "status": state["status"],
        }))
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({
                "type": "update",
                "overlays": state["overlays"],
                "weather": state["weather"],
                "status": state["status"],
                "last_updated": state["last_updated"],
            }))
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)