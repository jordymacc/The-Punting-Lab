"""
Racing.com Live Odds Scraper — diagnostic version to find correct selectors.
"""
from __future__ import annotations
import asyncio
import re
from typing import Dict

def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())

def _clean_odds(text: str) -> float:
    if not text or text.strip() in ("N/A", "—", "-", ""):
        return 0.0
    try:
        val = float(text.replace("$","").replace(",","").strip())
        return val if val > 1.0 else 0.0
    except ValueError:
        return 0.0

async def scrape_live_odds(url: str = "https://www.racing.com/todays-racing") -> Dict[str, dict]:
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError as e:
        print(f"[Odds] Missing dependency: {e}")
        return {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            context = await browser.new_context(viewport={"width":1920,"height":1080}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
            page = await context.new_page()
            print(f"[Odds] Navigating to {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                await page.click("#onetrust-accept-btn-handler", timeout=3000)
                await asyncio.sleep(0.5)
            except Exception:
                pass
            await asyncio.sleep(5)
            html = await page.content()
            print(f"[Odds] Page length: {len(html)}")
            idx = html.lower().find("runner")
            if idx > 0:
                snippet = html[max(0,idx-200):idx+2800]
                classes = list(dict.fromkeys(re.findall(r'class[Name]*=["\']([^"\']+)["\']', snippet)))[:20]
                print(f"[Odds] Classes near runner: {classes}")
                print(f"[Odds] Snippet: {snippet[:800]}")
            else:
                print("[Odds] runner not found, dumping body:")
                bi = html.find("<body")
                print(html[bi:bi+2000])
            await browser.close()
    except Exception as e:
        print(f"[Odds] Scrape failed: {e}")
    return {}

def inject_odds(races: list, odds_map: Dict[str, dict]) -> list:
    return races
