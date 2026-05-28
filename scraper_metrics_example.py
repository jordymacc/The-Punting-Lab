# Add this to your scraper.py

from racing_metrics import racing_tracker
import time

async def scrape_race_data(source: str, url: str):
    """Example scraping function with metrics tracking."""
    start_time = time.time()
    
    try:
        # Your existing scraping logic here
        response = await fetch_race_data(url)
        
        # Calculate data quality (example)
        data_quality = calculate_data_quality(response)
        
        # Track successful scraping
        response_time = time.time() - start_time
        racing_tracker.track_scraping_operation(
            source=source,
            success=True,
            response_time=response_time,
            data_quality=data_quality
        )
        
        # Track discovered races
        for race in response.get('races', []):
            racing_tracker.track_race_discovery(
                race_id=race['id'],
                track=race['track'],
                race_time=parse_datetime(race['start_time'])
            )
        
        return response
        
    except Exception as e:
        # Track failed scraping
        response_time = time.time() - start_time
        racing_tracker.track_scraping_operation(
            source=source,
            success=False,
            response_time=response_time,
            data_quality=0.0
        )
        raise

def calculate_data_quality(data):
    """Calculate data quality score (0-1)."""
    quality_score = 1.0
    
    # Check for missing data
    if not data.get('races'):
        quality_score -= 0.5
    
    # Check for incomplete race data
    for race in data.get('races', []):
        if not race.get('horses'):
            quality_score -= 0.1
        if not race.get('odds'):
            quality_score -= 0.1
    
    return max(0.0, quality_score)
