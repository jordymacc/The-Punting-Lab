import asyncio
from datetime import datetime
from scraper import get_race_fields
from weather import get_all_track_weather
from overlay_model import process_race
from database import SessionLocal, Horse, Race, WeatherData

state = {
    "races": [],
    "weather": {},
    "overlays": [],
    "last_updated": None,
    "status": "starting",
}

async def run_overlay_calc():
    try:
        if not state["races"]:
            print("Calculating overlays...")
            print("No races loaded yet, skipping overlay calc")
            return
        print("Calculating overlays...")
        all_overlays = []
        for race in state["races"]:
            weather = state["weather"].get(race["track"], {})
            horses = race.get("horses", [])
            if not horses:
                continue
            overlays = process_race(horses, weather)
            for o in overlays:
                o["race_id"] = race.get("race_id", "")
                o["track"] = race.get("track", "")
                o["race_number"] = race.get("race_number", 0)
                o["race_time"] = race.get("race_time", "")
                o["race_name"] = race.get("race_name", "")
            all_overlays.extend(overlays)
        state["overlays"] = sorted(
            all_overlays,
            key=lambda x: x.get("fair_value", 0),
            reverse=True
        )
        print(f"Overlay calc complete: {len(state['overlays'])} runners ranked")
    except Exception as e:
        print(f"Error in overlay calculation: {e}")

async def race_scraper_agent():
    while True:
        try:
            print("Running race scraper...")
            races = await get_race_fields()
            state["races"] = races
            state["last_updated"] = datetime.utcnow().isoformat()
            state["status"] = "running"
            save_races_to_db(races)
        except Exception as e:
            print(f"Race scraper error: {e}")
        await asyncio.sleep(300)

async def weather_agent():
    while True:
        try:
            print("Fetching weather data...")
            weather_list = await get_all_track_weather()
            for w in weather_list:
                state["weather"][w["track"]] = w
            save_weather_to_db(weather_list)
            print(f"Weather update complete: {len(weather_list)} tracks")
        except Exception as e:
            print(f"Weather error: {e}")
        await asyncio.sleep(600)

async def overlay_agent():
    # Wait until races are loaded
    waited = 0
    while not state["races"] and waited < 120:
        await asyncio.sleep(5)
        waited += 5
    # Now calculate
    while True:
        await run_overlay_calc()
        await asyncio.sleep(120)

async def odds_monitor_agent():
    previous_odds = {}
    while True:
        try:
            print("Monitoring odds movements...")
            for race in state["races"]:
                for horse in race.get("horses", []):
                    key = f"{race.get('race_id')}_{horse.get('horse_name')}"
                    current_odds = horse.get("tote_odds", 0)
                    if key in previous_odds and previous_odds[key] > 0 and current_odds > 0:
                        movement = ((current_odds - previous_odds[key]) / previous_odds[key]) * 100
                        if abs(movement) >= 15:
                            print(f"ODDS MOVE: {horse.get('horse_name')} "
                                  f"{previous_odds[key]} -> {current_odds} ({movement:.1f}%)")
                    previous_odds[key] = current_odds
        except Exception as e:
            print(f"Odds monitor error: {e}")
        await asyncio.sleep(60)

async def cleanup_agent():
    while True:
        try:
            db = SessionLocal()
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(hours=24)
            deleted = db.query(WeatherData).filter(
                WeatherData.recorded_at < cutoff
            ).delete()
            db.commit()
            db.close()
            print(f"Cleanup complete: removed {deleted} old weather records")
        except Exception as e:
            print(f"Cleanup error: {e}")
        await asyncio.sleep(3600)

def save_races_to_db(races):
    db = SessionLocal()
    try:
        for race in races:
            existing = db.query(Race).filter(Race.race_id == race["race_id"]).first()
            if not existing:
                db.add(Race(
                    race_id=race["race_id"],
                    track=race["track"],
                    race_number=race["race_number"],
                    race_time=race["race_time"],
                    distance=race["distance"],
                    condition=race["condition"],
                ))
            for horse in race.get("horses", []):
                existing_horse = db.query(Horse).filter(
                    Horse.race_id == race["race_id"],
                    Horse.horse_name == horse["horse_name"]
                ).first()
                if existing_horse:
                    existing_horse.tote_odds = horse.get("tote_odds", 0)
                    existing_horse.fixed_odds = horse.get("fixed_odds", 0)
                    existing_horse.updated_at = datetime.utcnow()
                else:
                    db.add(Horse(
                        race_id=race["race_id"],
                        horse_name=horse.get("horse_name", ""),
                        barrier=horse.get("barrier", 0),
                        jockey=horse.get("jockey", ""),
                        trainer=horse.get("trainer", ""),
                        weight=horse.get("weight", 0),
                        tote_odds=horse.get("tote_odds", 0),
                        fixed_odds=horse.get("fixed_odds", 0),
                    ))
        db.commit()
    except Exception as e:
        print(f"DB save error: {e}")
        db.rollback()
    finally:
        db.close()

def save_weather_to_db(weather_list):
    db = SessionLocal()
    try:
        for w in weather_list:
            db.add(WeatherData(
                track=w["track"],
                temperature=w["temperature"],
                humidity=w["humidity"],
                wind_speed=w["wind_speed"],
                conditions=w["conditions"],
            ))
        db.commit()
    except Exception as e:
        print(f"DB weather save error: {e}")
        db.rollback()
    finally:
        db.close()

async def scratch_detection_agent():
    """Checks for scratchings every 30 minutes and removes scratched runners"""
    while True:
        await asyncio.sleep(1800)  # wait 30 min before first check
        try:
            if not state["races"]:
                continue
            print("[Scratch] Checking for scratchings...")
            from scraper import get_race_form
            from datetime import datetime as dt
            today = dt.now().strftime("%Y-%m-%d")
            total_removed = 0

            for race in state["races"]:
                slug = race.get("race_id", "").split("_")[0]
                race_number = race.get("race_number")
                if not slug or not race_number:
                    continue

                form_data = await get_race_form(today, slug, race_number)
                if not form_data or not isinstance(form_data, dict):
                    continue

                runners = form_data.get("runners") or []
                scratched_names = set()
                for r in runners:
                    if r and r.get("scratched"):
                        scratched_names.add(r.get("name", "").strip())

                if not scratched_names:
                    continue

                before = len(race["horses"])
                race["horses"] = [
                    h for h in race["horses"]
                    if h.get("horse_name", "").strip() not in scratched_names
                ]
                after = len(race["horses"])
                removed = before - after
                if removed > 0:
                    total_removed += removed
                    print(f"[Scratch] {race['track']} R{race['race_number']}: removed {removed} scratching(s) — {scratched_names}")

                await asyncio.sleep(0.3)

            if total_removed > 0:
                print(f"[Scratch] {total_removed} runners removed, recalculating overlays...")
                await run_overlay_calc()
                state["last_updated"] = __import__('datetime').datetime.utcnow().isoformat()
            else:
                print("[Scratch] No scratchings found")

        except Exception as e:
            print(f"[Scratch] Error: {e}")

async def start_all_agents():
    print("Starting background agents in 20 seconds...")
    await asyncio.sleep(20)
    print("Starting all background agents...")
    await asyncio.gather(
        race_scraper_agent(),
        weather_agent(),
        overlay_agent(),
        odds_monitor_agent(),
        cleanup_agent(),
        scratch_detection_agent(),
    )