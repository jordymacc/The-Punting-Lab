"""
Racing.com Live Odds Scraper — fixed diagnostic version.
"""
from __future__ import annotations
import asyncio
import re
import json
from typing import Dict, List

def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())

def _clean_odds(text: str) -> float:
    if not text or text.strip() in ("N/A", "—", "-", "", "SCR", "LSP"):
        return 0.0
    try:
        val = float(text.replace("$", "").replace(",", "").strip())
        return val if val > 1.0 else 0.0
    except ValueError:
        return 0.0

async def scrape_live_odds(url: str = "https://www.racing.com/todays-racing") -> Dict[str, dict]:
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError as e:
        print(f"[Odds] Missing dependency: {e}")
        return {}

    odds_map: Dict[str, dict] = {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                ]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Intercept API responses to grab odds data directly (most reliable)
            api_responses: List[dict] = []
            
            async def handle_response(response):
                try:
                    if "racing.com" in response.url and ("odds" in response.url.lower() or "race" in response.url.lower()):
                        body = await response.body()
                        try:
                            data = json.loads(body)
                            api_responses.append({"url": response.url, "data": data})
                            print(f"[API] Captured: {response.url[:80]}...")
                        except:
                            pass
                except Exception:
                    pass
            
            page.on("response", handle_response)

            print(f"[Odds] Navigating to {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PWTimeout:
                print("[Odds] Initial load timed out, continuing...")
            
            # Dismiss cookie banner
            try:
                await page.click("#onetrust-accept-btn-handler", timeout=3000)
                await asyncio.sleep(0.5)
            except Exception:
                pass

            # Wait for race cards to appear using multiple possible selectors
            selectors_to_try = [
                "[data-testid*='race']",
                "[data-testid*='card']",
                ".race-card",
                ".meeting-card",
                "[class*='RaceCard']",
                "[class*='race-card']",
                "article",  # common wrapper
                "[class*='Meeting']",
            ]
            
            found_selector = None
            for sel in selectors_to_try:
                try:
                    await page.wait_for_selector(sel, timeout=5000)
                    count = await page.locator(sel).count()
                    if count > 0:
                        found_selector = sel
                        print(f"[Odds] Found selector '{sel}' with {count} elements")
                        break
                except Exception:
                    continue
            
            if not found_selector:
                print("[Odds] No race card selectors found. Dumping visible text...")
                text = await page.locator("body").inner_text()
                print(text[:2000])
                await browser.close()
                return {}

            # Give extra time for odds to populate
            await asyncio.sleep(3)

            # Strategy 1: Try to extract from page text/structure
            print("\n[Odds] === DOM ANALYSIS ===")
            
            # Get all links that look like race links
            race_links = await page.locator("a[href*='/form-guide/']").all()
            print(f"[Odds] Found {len(race_links)} form-guide links")
            
            # Get all text on page to see horse names
            all_text = await page.locator("body").inner_text()
            print(f"[Odds] Page text length: {len(all_text)} chars")
            
            # Look for dollar-sign odds patterns
            odds_patterns = re.findall(r'\$\d+\.\d+|\d+\.\d+0', all_text[:50000])
            print(f"[Odds] Found {len(odds_patterns)} potential odds values: {odds_patterns[:20]}")
            
            # Strategy 2: Try common odds container selectors
            odds_selectors = [
                "text=$",  # Playwright text selector for dollar signs
                "[class*='odds']",
                "[class*='Odds']",
                "[data-testid*='odds']",
                "span:has-text('$')",
                "div:has-text('$')",
            ]
            
            for sel in odds_selectors:
                try:
                    count = await page.locator(sel).count()
                    if count > 0:
                        print(f"[Odds] Selector '{sel}' matches {count} elements")
                        if count < 50:
                            texts = await page.locator(sel).all_inner_texts()
                            print(f"    Sample: {texts[:10]}")
                except Exception as e:
                    print(f"[Odds] Selector '{sel}' failed: {e}")

            # Strategy 3: Check for JSON data in script tags (Next.js/common pattern)
            scripts = await page.locator("script").all_inner_texts()
            print(f"\n[Odds] Found {len(scripts)} script tags")
            for i, script in enumerate(scripts[:5]):
                if len(script) > 500 and ("odds" in script.lower() or "runner" in script.lower() or "horse" in script.lower()):
                    print(f"[Odds] Script {i} looks relevant ({len(script)} chars)")
                    print(f"    Preview: {script[:500]}")
            
            # Strategy 4: Check API responses captured earlier
            print(f"\n[Odds] === API RESPONSES ===")
            print(f"[Odds] Captured {len(api_responses)} API responses")
            for resp in api_responses[:5]:
                print(f"    URL: {resp['url'][:100]}")
                data_preview = json.dumps(resp['data'])[:300] if isinstance(resp['data'], dict) else str(resp['data'])[:300]
                print(f"    Data preview: {data_preview}...")

            # Take screenshot for visual debugging
            await page.screenshot(path="/tmp/racing_debug.png", full_page=True)
            print("[Odds] Screenshot saved to /tmp/racing_debug.png")

            await browser.close()

    except Exception as e:
        print(f"[Odds] Scrape failed: {e}")
        import traceback
        traceback.print_exc()

    return odds_map

def inject_odds(races: list, odds_map: Dict[str, dict]) -> list:
    return races


if __name__ == "__main__":
    asyncio.run(scrape_live_odds())
