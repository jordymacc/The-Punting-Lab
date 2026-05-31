import asyncio
from datetime import datetime
from racing_com_scraper import racing_com_scraper

async def racing_com_odds_agent():
    """Background agent that scrapes Racing.com live odds every 3 minutes."""
    print("[RacingCom Agent] Starting...")
    
    # Wait for initial data load
    await asyncio.sleep(30)
    
    while True:
        try:
            print(f"[RacingCom Agent] Scraping live odds at {datetime.now().strftime('%H:%M:%S')}")
            
            all_odds = await racing_com_scraper.scrape_all_odds()
            
            if all_odds:
                total_runners = sum(len(r.get("runners", [])) for r in all_odds.values())
                print(f"[RacingCom Agent] Scraped {len(all_odds)} races, {total_runners} runners")
            else:
                print("[RacingCom Agent] No odds data available")
                
        except Exception as e:
            print(f"[RacingCom Agent] Error: {e}")
        
        # Wait 3 minutes before next scrape
        await asyncio.sleep(180)
