"""
Racing.com Live Odds Scraper — integrated for The Punting Lab backend.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import re
from typing import Dict, List

logger = logging.getLogger("odds_scraper")

def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())

SELECTOR_CHAINS: Dict[str, List[str]] = {
    "race_cards": [
        "[data-testid='race-card']", ".race-card", ".race-list__item",
        "[class*='RaceCard']", "[class*='race-card']", ".race",
    ],
    "race_time": [
        ".race-card__time", "[data-testid='race-time']", ".race-header__time",
        "time", "[class*='time']",
    ],
    "runner_row": [
        "tr[data-runner]", ".odds-table__row", ".runner-odds__row",
        "tbody tr", "tr",
    ],
    "horse_name": [
        ".runner-name", "[data-testid='runner-name']", ".odds-table__name a",
        "a[href*='horse']", "td:nth-child(2)",
    ],
    "win_odds": [
        ".odds-win", "[data-testid='odds-win']", ".odds-table__win",
        "[class*='win'][class*='odd']",
    ],
    "place_odds": [
        ".odds-place", "[data-testid='odds-place']", ".odds-table__place",
        "[class*='place'][class*='odd']",
    ],
    "cookie_accept": [
        "[data-testid='cookie-accept']", "#onetrust-accept-btn-handler",
        ".cookie-banner__accept", "button[class*='accept']",
    ],
}

def _clean_odds(text: str) -> float:
    if not text or text.strip() in ("N/A", "—", "-", ""):
        return 0.0
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return val if val > 1.0 else 0.0
    except ValueError:
        return 0.0

def _select_first(soup, selectors):
    for sel in selectors:
        try:
            el = soup.select_one(sel)
            if el:
                return el
        except Exception:
            continue
    return None

def _select_all(soup, selectors):
    for sel in selectors:
        try:
            els = soup.select(sel)
            if els:
                return els
        except Exception:
            continue
    return []

async def scrape_live_odds(url: str = "https://www.racing.com/todays-racing") -> Dict[str, dict]:
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"[Odds] Missing dependency: {e}")
        return {}

    odds_map: Dict[str, dict] = {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

            print(f"[Odds] Navigating to {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            for sel in SELECTOR_CHAINS["cookie_accept"]:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(0.5)
                        break
                except Exception:
                    continue

            loaded = False
            for sel in SELECTOR_CHAINS["race_cards"]:
                try:
                    await page.wait_for_selector(sel, timeout=15000, state="visible")
                    loaded = True
                    print(f"[Odds] Race cards found with selector: {sel}")
                    break
                except Exception:
                    continue

            try:
                title = await page.title()
                html = await page.content()
                print(f"[Odds] Page title: {title}, length: {len(html)}")
                classes = list(dict.fromkeys(re.findall(r'class="([^"]*?)"', html[:8000])))[:10]
                print(f"[Odds] Sample classes: {classes}")
            except Exception:
                pass

            if not loaded:
                print("[Odds] No race cards matched any selector")
                await browser.close()
                return {}

            await asyncio.sleep(2)
            soup = BeautifulSoup(await page.content(), "html.parser")
            await browser.close()

            race_cards = _select_all(soup, SELECTOR_CHAINS["race_cards"])
            print(f"[Odds] Found {len(race_cards)} race cards")

            seen_sigs = set()
            for card in race_cards:
                race_time = ""
                rt = _select_first(card, SELECTOR_CHAINS["race_time"])
                if rt:
                    race_time = rt.get_text(strip=True)

                rows = _select_all(card, SELECTOR_CHAINS["runner_row"])
                for row in rows:
                    try:
                        name_el = _select_first(row, SELECTOR_CHAINS["horse_name"])
                        if not name_el:
                            continue
                        horse_name = name_el.get_text(strip=True)
                        if not horse_name or horse_name.lower() in ("horse", "runner", "n/a", ""):
                            continue
                        sig = hashlib.md5(horse_name.lower().encode()).hexdigest()[:8]
                        if sig in seen_sigs:
                            continue
                        seen_sigs.add(sig)
                        win_el   = _select_first(row, SELECTOR_CHAINS["win_odds"])
                        place_el = _select_first(row, SELECTOR_CHAINS["place_odds"])
                        win   = _clean_odds(win_el.get_text(strip=True)   if win_el   else "")
                        place = _clean_odds(place_el.get_text(strip=True) if place_el else "")
                        key = normalise(horse_name)
                        odds_map[key] = {"horse_name": horse_name, "win": win, "place": place, "race_time": race_time}
                    except Exception as e:
                        print(f"[Odds] Row parse error: {e}")
                        continue

            print(f"[Odds] Scraped odds for {len(odds_map)} runners")

    except Exception as e:
        print(f"[Odds] Scrape failed: {e}")

    return odds_map


def inject_odds(races: list, odds_map: Dict[str, dict]) -> list:
    if not odds_map:
        return races
    matched = 0
    for race in races:
        for horse in race.get("horses", []):
            key = normalise(horse.get("horse_name", ""))
            if key in odds_map and odds_map[key]["win"] > 0:
                horse["tote_odds"]  = odds_map[key]["win"]
                horse["fixed_odds"] = odds_map[key]["win"]
                matched += 1
    print(f"[Odds] Injected odds into {matched} horses")
    return races
