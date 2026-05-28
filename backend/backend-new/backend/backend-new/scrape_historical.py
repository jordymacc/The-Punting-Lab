import asyncio
from datetime import datetime, timedelta
from scraper import get_meetings, get_race_form, parse_runners
from overlay_model import process_race
from database import SessionLocal, RaceResult


async def inspect_api_response(date_str: str):
    print(f"\n🔍 INSPECTING API RESPONSE FOR {date_str}")
    print("-" * 50)

    meetings = await get_meetings(date_str)
    if not meetings:
        print("❌ No meetings found")
        return

    meeting = meetings[0]
    slug = meeting.get("slug", "")
    track = meeting.get("track", "")
    races = meeting.get("races", [])

    if not races:
        print("❌ No races found")
        return

    race_number = races[0].get("raceNumber", 1)
    print(f"🏟️  Inspecting: {track} R{race_number}")

    form_data = await get_race_form(date_str, slug, race_number)

    if not form_data:
        print("❌ No form data returned")
        return

    print(f"\n📋 Top-level keys: {list(form_data.keys())}")

    for key in ["result", "results", "finishers", "placements", "finishOrder", "finishingOrder", "exoticResults"]:
        if key in form_data:
            print(f"🏆 Found '{key}': {form_data[key]}")

    runners = form_data.get("runners", [])
    if runners:
        print(f"\n🐴 {len(runners)} runners found")
        first = runners[0]
        print(f"📋 Runner keys: {list(first.keys())}")
        print(f"📋 First runner sample:")
        for k, v in first.items():
            print(f"   {k}: {v}")

        position_fields = [
            "position", "finishingPosition", "finishPosition",
            "place", "result", "finish", "placing", "rank",
            "finalPosition", "racePosition", "outcome",
        ]
        print(f"\n🔍 Checking position fields across all runners:")
        for field in position_fields:
            values = [r.get(field) for r in runners if r and isinstance(r, dict)]
            non_none = [v for v in values if v is not None]
            if non_none:
                print(f"   ✅ '{field}' found: {non_none[:5]}")

    print(f"\n🔍 Checking if /v1/results endpoint exists...")
    try:
        import aiohttp
        BASE_URL = "https://api.formfav.com"
        API_KEY = "fk_7854bdf2477c56c2f75e453489bd9ee867209c06d00494df960bf4d3d2b65da1"
        HEADERS = {"X-API-Key": API_KEY}

        async with aiohttp.ClientSession() as session:
            for endpoint in ["/v1/results", "/v1/form/results"]:
                url = f"{BASE_URL}{endpoint}"
                params = {
                    "date": date_str,
                    "track": slug,
                    "race": str(race_number),
                    "race_code": "gallops",
                    "country": "au",
                }
                try:
                    async with session.get(url, headers=HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        print(f"   {endpoint} → Status {resp.status}")
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                print(f"   📋 Keys: {list(data.keys())}")
                            print(f"   📋 Data: {str(data)[:500]}")
                except Exception as e:
                    print(f"   {endpoint} → Error: {e}")
    except Exception as e:
        print(f"   Error checking endpoints: {e}")

    print("\n" + "=" * 50)
    print("✅ Inspection complete. Review output above.")
    print("=" * 50)


async def inspect_web_results(date_str: str):
    import aiohttp
    import re

    url = f"https://www.racingpost.com/results/{date_str}/au"
    print(f"\n🔍 INSPECTING WEB RESULTS FOR {date_str}")
    print(f"📍 URL: {url}")
    print("-" * 50)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                print(f"Status: {resp.status}")
                if resp.status != 200:
                    print("❌ Could not fetch page")
                else:
                    html = await resp.text()
                    print(f"Page length: {len(html)} chars")

                    with open("debug_results_page.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print("✅ Saved to debug_results_page.html")

                    keywords = [
                        "1st", "2nd", "3rd",
                        "winner", "placed", "finished",
                        "result", "position",
                        "finishing", "first-past",
                    ]
                    for kw in keywords:
                        matches = [m.start() for m in re.finditer(kw, html, re.IGNORECASE)]
                        if matches:
                            print(f"  🔎 '{kw}' found {len(matches)} times")
                            pos = matches[0]
                            snippet = html[max(0, pos - 50):pos + 80].replace("\n", " ")
                            print(f"     → ...{snippet}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    url2 = f"https://www.racing.com/results/{date_str}"
    print(f"\n📍 Also trying: {url2}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url2, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    html2 = await resp.text()
                    print(f"Page length: {len(html2)} chars")
                    with open("debug_racing_com.html", "w", encoding="utf-8") as f:
                        f.write(html2)
                    print("✅ Saved to debug_racing_com.html")
                else:
                    print("❌ Could not fetch")
    except Exception as e:
        print(f"❌ Error: {e}")


async def extract_results(form_data: dict) -> dict:
    runners = form_data.get("runners", [])
    if not runners:
        return {}

    position_fields = [
        "position", "finishingPosition", "finishPosition",
        "place", "placing", "rank", "finalPosition",
        "racePosition", "outcome",
    ]

    for field in position_fields:
        placed = {}
        for r in runners:
            if not r or not isinstance(r, dict):
                continue
            pos = r.get(field)
            name = r.get("name", "")
            if pos is not None and name:
                try:
                    pos_int = int(pos)
                    if pos_int == 1:
                        placed["winner"] = name
                    elif pos_int == 2:
                        placed["second"] = name
                    elif pos_int == 3:
                        placed["third"] = name
                except (ValueError, TypeError):
                    pass
        if placed.get("winner"):
            print(f"     → Extracted from field '{field}'")
            return placed

    for key in ["result", "results", "finishers", "placements", "finishOrder", "finishingOrder"]:
        val = form_data.get(key)
        if not val:
            continue

        if isinstance(val, dict):
            winner = val.get("first") or val.get("winner") or val.get("1st") or val.get("1") or ""
            second = val.get("second") or val.get("2nd") or val.get("2") or ""
            third = val.get("third") or val.get("3rd") or val.get("3") or ""
            if winner:
                print(f"     → Extracted from race-level '{key}' (dict)")
                return {"winner": winner, "second": second, "third": third}

        elif isinstance(val, list) and len(val) >= 1:
            def get_name(item):
                if isinstance(item, dict):
                    return item.get("name", item.get("horse_name", ""))
                return str(item)
            print(f"     → Extracted from race-level '{key}' (list)")
            return {
                "winner": get_name(val[0]),
                "second": get_name(val[1]) if len(val) > 1 else "",
                "third": get_name(val[2]) if len(val) > 2 else "",
            }

    return {}


async def process_historical_race(date_str, track, slug, race_number, condition):
    race_id = f"{slug}_{race_number}_{date_str}"

    db = SessionLocal()
    existing = db.query(RaceResult).filter(RaceResult.race_id == race_id).first()
    db.close()
    if existing:
        print(f"  ⏭️  {track} R{race_number} — already processed, skipping")
        return None

    form_data = await get_race_form(date_str, slug, race_number)
    if not form_data:
        print(f"  ❌ {track} R{race_number} — no form data")
        return None

    runners = form_data.get("runners", [])
    if not runners:
        print(f"  ❌ {track} R{race_number} — no runners")
        return None

    results = await extract_results(form_data)
    if not results or not results.get("winner"):
        print(f"  ⚠️  {track} R{race_number} — no result data (race not run yet?)")
        return None

    winner = results.get("winner", "")
    second = results.get("second", "")
    third = results.get("third", "")

    horses = parse_runners(runners, condition)
    if not horses:
        print(f"  ❌ {track} R{race_number} — no active runners after parse")
        return None

    overlays = process_race(horses, {})

    model_top_pick = ""
    if overlays:
        model_top_pick = overlays[0].get("horse_name", "")

    model_won = False
    model_placed = False
    if model_top_pick and winner:
        model_won = model_top_pick.lower() == winner.lower()
        model_placed = model_top_pick.lower() in [winner.lower(), second.lower(), third.lower()]

    db = SessionLocal()
    try:
        db.add(RaceResult(
            race_id=race_id,
            track=track,
            race_number=race_number,
            race_date=date_str,
            winner=winner,
            second=second,
            third=third,
            model_top_pick=model_top_pick,
            model_top_pick_won=model_won,
            model_top_pick_placed=model_placed,
        ))
        db.commit()
    except Exception as e:
        print(f"  ❌ DB error: {e}")
        db.rollback()
    finally:
        db.close()

    if model_won:
        outcome = "✅ WIN"
    elif model_placed:
        outcome = "📍 PLACED"
    else:
        outcome = "❌ LOST"

    print(f"  {outcome} — {track} R{race_number}: Model picked [{model_top_pick}] — Winner: {winner}")

    return {
        "track": track,
        "race_number": race_number,
        "model_top_pick": model_top_pick,
        "winner": winner,
        "won": model_won,
        "placed": model_placed,
    }


async def backfill_history(days: int = 7):
    print("=" * 55)
    print("📊 HISTORICAL BACKFILL STARTING")
    print(f"   Period: last {days} days")
    print("=" * 55)

    stats = {"wins": 0, "places": 0, "losses": 0, "races": 0, "skipped": 0}

    for days_ago in range(1, days + 1):
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime("%Y-%m-%d")

        print(f"\n📅 Processing {date_str}...")

        meetings = await get_meetings(date_str)
        if not meetings:
            print(f"  ⚠️  No meetings found for {date_str}")
            continue

        print(f"  🏟️  Found {len(meetings)} meetings")

        for meeting in meetings:
            if not meeting or not isinstance(meeting, dict):
                continue

            slug = meeting.get("slug", "")
            track = meeting.get("track", "Unknown")
            meeting_races = meeting.get("races", [])

            if not slug:
                continue

            for race_info in meeting_races:
                if not race_info or not isinstance(race_info, dict):
                    continue
                if race_info.get("abandoned"):
                    continue

                race_number = race_info.get("raceNumber")
                if not race_number:
                    continue

                condition = race_info.get("condition", "Good")

                result = await process_historical_race(
                    date_str, track, slug, race_number, condition
                )

                if result:
                    stats["races"] += 1
                    if result["won"]:
                        stats["wins"] += 1
                    elif result["placed"]:
                        stats["places"] += 1
                    else:
                        stats["losses"] += 1
                else:
                    stats["skipped"] += 1

                await asyncio.sleep(0.3)

    total = stats["races"]
    win_pct = round(stats["wins"] / total * 100, 1) if total else 0
    place_pct = round(stats["places"] / total * 100, 1) if total else 0
    loss_pct = round(stats["losses"] / total * 100, 1) if total else 0

    print("\n" + "=" * 55)
    print("📊 HISTORICAL BACKFILL COMPLETE")
    print("=" * 55)
    print(f"  Total Races:  {total}")
    print(f"  Model Wins:   {stats['wins']}  ({win_pct}%)")
    print(f"  Model Places: {stats['places']}  ({place_pct}%)")
    print(f"  Model Losses: {stats['losses']}  ({loss_pct}%)")
    print(f"  Skipped:      {stats['skipped']}")
    print("=" * 55)

    return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        days_ago = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        asyncio.run(inspect_api_response(date_str))

    elif len(sys.argv) > 1 and sys.argv[1] == "inspect-web":
        days_ago = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        asyncio.run(inspect_web_results(date_str))

    elif len(sys.argv) > 1 and sys.argv[1] == "backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        asyncio.run(backfill_history(days))

    else:
        print("Usage:")
        print("  python scrape_historical.py inspect [days_ago]      # Inspect FormFav API")
        print("  python scrape_historical.py inspect-web [days_ago]  # Inspect web results")
        print("  python scrape_historical.py backfill [days]         # Run full backfill")