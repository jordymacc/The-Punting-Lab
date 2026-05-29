#!/usr/bin/env python3
"""
Racing.com Live Odds Scraper — integrated version for The Punting Lab backend.
Scrapes live win/place odds from Racing.com and returns a dict keyed by
normalised horse name for fast lookup during overlay calculation.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger("odds_scraper")

# ── normalise horse name for fuzzy matching ──────────────────────────────────
def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())

# ── selectors ────────────────────────────────────────────────────────────────
SELECTORS = {
    "race_cards":   "[data-testid='race-card'], .race-card, .race-list__item",
    "race_number":  ".race-card__number, [data-testid='race-number'], .race-header__number",
    "race_time":    ".race-card__time, [data-testid='race-time'], .race-header__time",
    "runner_row":   "tr[data-runner], .odds-table__row, .runner-odds__row, tbody tr",
    "horse_name":   ".runner-name a, [data-testid='runner-name'], .odds-table__name a, .runner-name",
    "win_odds":     ".odds-win, [data-testid='odds-win'], .odds-table__win, [class*='win']",
    "place_odds":   ".odds-place, [data-testid='odds-place'], .odds-table__place, [class*='place']",
    "cookie_accept":"[data-testid='cookie-accept'], #onetrust-accept-btn-handler, .cookie-banner__accept",
}

def _clean_odds(text: str) -> float:
    """Convert odds text like '$4.50' or '4.50' to float. Returns 0.0 if invalid."""
    if not text or text in ("N/A", "—", "-", ""):
        return 0.0
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return val if val > 1.0 else 0.0
    except ValueError:
        return 0.0

async def scrape_live_odds(url: str = "https://www.racing.com/todays-racing") -> Dict[str, dict]:
    """
    Scrape live odds from Racing.com.
    Returns dict: { normalised_horse_name: { "win": float, "place": float, "race_time": str } }
    Returns empty dict on any failure — caller falls back to no-odds mode gracefully.
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("[Odds] Playwright not installed — skipping live odds scrape")
        return {}

    odds_map: Dict[str, dict] = {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

            logger.info(f"[Odds] Navigating to {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                logger.warning("[Odds] Page load timeout — trying domcontentloaded")
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # dismiss cookie banner
            try:
                btn = await page.query_selector(SELECTORS["cookie_accept"])
                if btn:
                    await btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # wait for content
            try:
                await page.wait_for_selector(SELECTORS["race_cards"], timeout=15000, state="visible")
                await asyncio.sleep(2)
            except PWTimeout:
                logger.warning("[Odds] Race cards not found — page structure may have changed")
                await browser.close()
                return {}

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(await page.content(), "html.parser")
            await browser.close()

            race_cards = soup.select(SELECTORS["race_cards"])
            logger.info(f"[Odds] Found {len(race_cards)} race cards")

            for card in race_cards:
                race_time = ""
                try:
                    rt = card.select_one(SELECTORS["race_time"])
                    race_time = rt.get_text(strip=True) if rt else ""
                except Exception:
                    pass

                rows = card.select(SELECTORS["runner_row"])
                for row in rows:
                    try:
                        name_el = row.select_one(SELECTORS["horse_name"])
                        if not name_el:
                            continue
                        horse_name = name_el.get_text(strip=True)
                        if not horse_name or horse_name.lower() in ("horse", "runner", "n/a"):
                            continue

                        win_el   = row.select_one(SELECTORS["win_odds"])
                        place_el = row.select_one(SELECTORS["place_odds"])
                        win   = _clean_odds(win_el.get_text(strip=True)   if win_el   else "")
                        place = _clean_odds(place_el.get_text(strip=True) if place_el else "")

                        key = normalise(horse_name)
                        odds_map[key] = {
                            "horse_name": horse_name,
                            "win":        win,
                            "place":      place,
                            "race_time":  race_time,
                        }
                    except Exception:
                        continue

            logger.info(f"[Odds] Scraped odds for {len(odds_map)} runners")

    except Exception as e:
        logger.error(f"[Odds] Scrape failed: {e}")

    return odds_map


def inject_odds(races: list, odds_map: Dict[str, dict]) -> list:
    """
    Walk every horse in every race and inject tote_odds + fixed_odds
    from the scraped odds_map. Matched by normalised name.
    Falls back gracefully if no match found.
    """
    if not odds_map:
        return races

    matched = 0
    for race in races:
        for horse in race.get("horses", []):
            key = normalise(horse.get("horse_name", ""))
            if key in odds_map:
                o = odds_map[key]
                if o["win"] > 0:
                    horse["tote_odds"]  = o["win"]
                    horse["fixed_odds"] = o["win"]
                    matched += 1

    logger.info(f"[Odds] Injected odds into {matched} horses")
    return races