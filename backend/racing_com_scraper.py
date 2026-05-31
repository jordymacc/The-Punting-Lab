"""
Racing.com Live Odds Scraper
Uses Playwright to scrape live odds from racing.com race pages
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright

RACING_COM_BASE = "https://www.racing.com"

class RacingComScraper:
    """Scrape live odds from Racing.com using Playwright"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.odds_cache: Dict = {}
        self.last_update: Optional[datetime] = None
    
    async def _init_browser(self):
        """Initialize Playwright browser if not already running"""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
    
    async def scrape_meetings(self) -> List[Dict]:
        """Get all today's meetings from Racing.com"""
        await self._init_browser()
        page = await self.context.new_page()
        
        try:
            print("[RacingCom] Loading meetings page...")
            await page.goto(f"{RACING_COM_BASE}/race-day", wait_until="networkidle", timeout=30000)
            
            meetings = await page.evaluate("""
                () => {
                    const meetings = [];
                    const cards = document.querySelectorAll('.race-day-card, .meeting-card');
                    cards.forEach(card => {
                        const nameEl = card.querySelector('h3, .meeting-name');
                        const linkEl = card.querySelector('a[href*="/races/"]');
                        if (nameEl && linkEl) {
                            meetings.push({
                                name: nameEl.textContent.trim(),
                                href: linkEl.href,
                                track: nameEl.textContent.trim().split(' ')[0]
                            });
                        }
                    });
                    return meetings;
                }
            """)
            
            print(f"[RacingCom] Found {len(meetings)} meetings")
            return meetings
            
        except Exception as e:
            print(f"[RacingCom] Error scraping meetings: {e}")
            return []
        finally:
            await page.close()
    
    async def scrape_race_odds(self, race_url: str) -> Dict:
        """Scrape live odds for a specific race"""
        await self._init_browser()
        page = await self.context.new_page()
        
        try:
            print(f"[RacingCom] Loading race: {race_url}")
            await page.goto(race_url, wait_until="networkidle", timeout=30000)
            
            # Wait for odds to load
            await page.wait_for_selector('.odds, .price', timeout=10000).catch(lambda: None)
            
            # Extract runners and odds
            runners = await page.evaluate("""
                () => {
                    const runners = [];
                    const rows = document.querySelectorAll('.runner-row, .horse-row, tr');
                    
                    rows.forEach(row => {
                        const nameEl = row.querySelector('.runner-name, .horse-name, td:nth-child(2)');
                        const oddsEl = row.querySelector('.odds, .price, .current-odds');
                        
                        if (nameEl && oddsEl) {
                            const oddsText = oddsEl.textContent.trim().replace('$', '');
                            const odds = parseFloat(oddsText);
                            
                            runners.push({
                                name: nameEl.textContent.trim(),
                                odds: isNaN(odds) ? null : odds
                            });
                        }
                    });
                    return runners;
                }
            """)
            
            print(f"[RacingCom] Found {len(runners)} runners with odds")
            return {
                "url": race_url,
                "runners": runners,
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"[RacingCom] Error scraping race odds: {e}")
            return {"url": race_url, "runners": [], "error": str(e)}
        finally:
            await page.close()
    
    async def scrape_all_odds(self) -> Dict:
        """Scrape odds for all races today"""
        meetings = await self.scrape_meetings()
        all_odds = {}
        
        for meeting in meetings[:5]:  # Limit to first 5 meetings
            try:
                race_url = meeting.get("href", "")
                if race_url:
                    odds = await self.scrape_race_odds(race_url)
                    all_odds[meeting["name"]] = odds
            except Exception as e:
                print(f"[RacingCom] Error processing {meeting.get('name')}: {e}")
        
        self.odds_cache = all_odds
        self.last_update = datetime.now()
        return all_odds
    
    def merge_with_overlays(self, overlays: List[Dict]) -> List[Dict]:
        """Merge Racing.com odds with overlay data"""
        if not self.odds_cache:
            return overlays
        
        # Build odds lookup map
        odds_map = {}
        for meeting_name, race_data in self.odds_cache.items():
            for runner in race_data.get("runners", []):
                horse_name = runner.get("name", "").strip().lower()
                odds_map[horse_name] = runner.get("odds")
        
        # Merge with overlays
        merged = []
        for overlay in overlays:
            horse_name = overlay.get("horse", "").strip().lower()
            if horse_name in odds_map and odds_map[horse_name]:
                overlay["live_odds"] = odds_map[horse_name]
                overlay["odds_source"] = "Racing.com"
                overlay["odds_updated"] = self.last_update.isoformat() if self.last_update else None
                
                # Calculate live overlay value
                fair_odds = overlay.get("fair_odds")
                if fair_odds:
                    try:
                        fair = float(fair_odds)
                        live = float(odds_map[horse_name])
                        if live > 0:
                            overlay["live_overlay"] = round(((fair - live) / live) * 100, 1)
                            overlay["live_value"] = "STRONG" if overlay["live_overlay"] > 20 else "GOOD" if overlay["live_overlay"] > 10 else "FAIR"
                    except (ValueError, TypeError):
                        pass
            
            merged.append(overlay)
        
        return merged
    
    async def close(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()


# Global instance
racing_com_scraper = RacingComScraper()
