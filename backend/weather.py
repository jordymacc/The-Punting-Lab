import aiohttp
import asyncio
from datetime import datetime

TRACKS = {
    "Flemington": {"lat": -37.7749, "lon": 144.9063},
    "Caulfield": {"lat": -37.8770, "lon": 145.0430},
    "Moonee Valley": {"lat": -37.7585, "lon": 144.9272},
    "Sandown": {"lat": -37.9453, "lon": 145.1065},
    "Randwick": {"lat": -33.8951, "lon": 151.2217},
    "Rosehill": {"lat": -33.8667, "lon": 151.0167},
    "Morphettville": {"lat": -34.9800, "lon": 138.5500},
    "Eagle Farm": {"lat": -27.4300, "lon": 153.0800},
}

async def get_weather(track_name: str) -> dict:
    coords = TRACKS.get(track_name, {"lat": -37.7749, "lon": 144.9063})
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={coords['lat']}&longitude={coords['lon']}"
        f"&current_weather=true&hourly=relativehumidity_2m,windspeed_10m"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                current = data.get("current_weather", {})
                hourly = data.get("hourly", {})
                humidity = hourly.get("relativehumidity_2m", [50])[0]
                return {
                    "track": track_name,
                    "temperature": current.get("temperature", 20.0),
                    "wind_speed": current.get("windspeed", 0.0),
                    "humidity": humidity,
                    "conditions": interpret_conditions(current.get("weathercode", 0)),
                    "recorded_at": datetime.utcnow().isoformat(),
                }
    except Exception as e:
        print(f"Weather fetch error for {track_name}: {e}")
        return default_weather(track_name)

def interpret_conditions(code: int) -> str:
    if code == 0:
        return "Clear"
    elif code in range(1, 4):
        return "Partly Cloudy"
    elif code in range(51, 68):
        return "Rainy"
    elif code in range(71, 78):
        return "Snow"
    elif code in range(80, 100):
        return "Showers"
    else:
        return "Overcast"

def default_weather(track_name: str) -> dict:
    return {
        "track": track_name,
        "temperature": 20.0,
        "wind_speed": 10.0,
        "humidity": 55.0,
        "conditions": "Unknown",
        "recorded_at": datetime.utcnow().isoformat(),
    }

async def get_all_track_weather() -> list:
    tasks = [get_weather(track) for track in TRACKS]
    return await asyncio.gather(*tasks)