import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone

BASE_URL = "https://api.formfav.com"
API_KEY = "fk_7854bdf2477c56c2f75e453489bd9ee867209c06d00494df960bf4d3d2b65da1"

HEADERS = {"X-API-Key": API_KEY}

async def get_meetings(date: str) -> list:
    url = f"{BASE_URL}/v1/form/meetings"
    params = {"date": date, "race_code": "gallops"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    print(f"[Meetings] API error {resp.status} for {date}")
                    return []
                data = await resp.json()
                meetings = data.get("meetings", [])
                au_meetings = [m for m in meetings if m and m.get("country") == "au" and not m.get("abandoned")]
                print(f"[Meetings] {date}: Found {len(au_meetings)} AU meetings")
                return au_meetings
    except Exception as e:
        print(f"[Meetings] Error for {date}: {e}")
        return []

async def get_race_form(date: str, track_slug: str, race_number: int) -> dict:
    url = f"{BASE_URL}/v1/form"
    params = {"date": date, "track": track_slug, "race": str(race_number), "race_code": "gallops", "country": "au"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
                return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[Form] Error {track_slug} R{race_number}: {e}")
        return {}

def parse_form_string(form: str):
    if not form:
        return None
    for ch in reversed(form):
        if ch.isdigit():
            return int(ch)
    return None

def parse_runners(runners: list, condition: str) -> list:
    horses = []
    for r in runners:
        if not r or not isinstance(r, dict) or r.get("scratched"):
            continue
        stats = r.get("stats") or {}
        overall = stats.get("overall") or {}
        track_stats = stats.get("track") or {}
        distance_stats = stats.get("distance") or {}
        condition_stats = stats.get("condition") or {}
        horses.append({
            "horse_name": r.get("name") or "Unknown",
            "barrier": r.get("barrier") or 0,
            "jockey": r.get("jockey") or "",
            "trainer": r.get("trainer") or "",
            "weight": r.get("weight") or 56.0,
            "tote_odds": 0.0,
            "fixed_odds": 0.0,
            "last_finish": parse_form_string(r.get("form") or ""),
            "days_since_last_run": None,
            "condition": condition,
            "win_percent": overall.get("winPercent") or 0.0,
            "place_percent": overall.get("placePercent") or 0.0,
            "track_win_percent": track_stats.get("winPercent") or 0.0,
            "distance_win_percent": distance_stats.get("winPercent") or 0.0,
            "condition_win_percent": condition_stats.get("winPercent") or 0.0,
            "career_starts": overall.get("starts") or 0,
            "form_string": r.get("form") or "",
        })
    return horses

async def fetch_races_for_date(date: str) -> list:
    meetings = await get_meetings(date)
    if not meetings:
        return []
    races = []
    for meeting in meetings:
        if not meeting or not isinstance(meeting, dict):
            continue
        slug = meeting.get("slug") or ""
        track = meeting.get("track") or "Unknown"
        if not slug:
            continue
        for race_info in (meeting.get("races") or []):
            if not race_info or race_info.get("abandoned"):
                continue
            race_number = race_info.get("raceNumber")
            if not race_number:
                continue
            condition = race_info.get("condition") or "Good"
            distance = race_info.get("distance") or "Unknown"
            race_name = race_info.get("raceName") or ""
            start_time = race_info.get("startTime") or ""
            try:
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                race_time = dt.astimezone().strftime("%H:%M")
            except:
                race_time = "00:00"
            form_data = await get_race_form(date, slug, race_number)
            if not form_data:
                continue
            runners = form_data.get("runners") or []
            horses = parse_runners(runners, condition)
            if not horses:
                continue
            races.append({
                "race_id": f"{slug}_{race_number}_{date}",
                "track": track,
                "race_number": race_number,
                "race_name": race_name,
                "race_time": race_time,
                "race_date": date,
                "distance": distance,
                "condition": condition,
                "horses": horses,
            })
            print(f"[Scraper] Loaded {track} R{race_number} ({date}) — {len(horses)} runners")
            await asyncio.sleep(0.3)
    return races

async def get_race_fields() -> list:
    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    print(f"[Scraper] Fetching races for: {', '.join(dates)}")
    all_races = []
    for date in dates:
        races = await fetch_races_for_date(date)
        all_races.extend(races)
        if date != dates[-1]:
            await asyncio.sleep(1)
    if not all_races:
        print("[Scraper] No races found, using mock data")
        return get_mock_races()
    print(f"[Scraper] Total: {len(all_races)} races loaded")
    return all_races

def get_mock_races() -> list:
    return [{"race_id": "flemington_1_mock", "track": "Flemington", "race_number": 1, "race_name": "Mock Race", "race_time": "12:30", "race_date": datetime.now().strftime("%Y-%m-%d"), "distance": "1200m", "condition": "Good", "horses": get_mock_horses()}]

def get_mock_horses() -> list:
    return [
        {"horse_name": "Thunder Strike", "barrier": 1, "jockey": "J. McDonald", "trainer": "C. Waller", "weight": 57.0, "tote_odds": 3.5, "fixed_odds": 3.2, "last_finish": 1, "days_since_last_run": 14, "win_percent": 0.40, "place_percent": 0.70, "track_win_percent": 0.50, "distance_win_percent": 0.45, "condition_win_percent": 0.40, "career_starts": 20, "form_string": "11211", "condition": "Good"},
        {"horse_name": "Silver Arrow", "barrier": 3, "jockey": "D. Oliver", "trainer": "L. Freedman", "weight": 56.5, "tote_odds": 5.0, "fixed_odds": 4.8, "last_finish": 2, "days_since_last_run": 21, "win_percent": 0.30, "place_percent": 0.60, "track_win_percent": 0.35, "distance_win_percent": 0.30, "condition_win_percent": 0.30, "career_starts": 15, "form_string": "21321", "condition": "Good"},
    ]
