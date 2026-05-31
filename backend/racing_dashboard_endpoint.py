# Add this to your main.py imports
from racing_metrics import racing_tracker

@app.get("/metrics/racing")
async def racing_metrics():
    """Get racing-specific performance metrics."""
    return racing_tracker.get_performance_summary()

@app.get("/metrics/racing/sources")
async def scraping_source_health():
    """Get detailed scraping source health."""
    sources = {}
    for source, metrics in racing_tracker.scraping_metrics.items():
        freshness = racing_tracker.get_data_freshness(source)
        success_rate = racing_tracker.get_scraping_success_rate(source)
        
        status = "healthy"
        if success_rate < 0.8:
            status = "warning"
        if success_rate < 0.5 or (freshness and freshness > 300):  # 5 minutes
            status = "critical"
        
        sources[source] = {
            'status': status,
            'success_rate': success_rate,
            'freshness_seconds': freshness,
            'average_response_time': metrics.average_response_time,
            'data_quality': metrics.data_quality_score
        }
    
    return sources

@app.get("/metrics/racing/predictions")
async def prediction_performance():
    """Get prediction accuracy metrics."""
    return {
        'overall_accuracy': racing_tracker.get_prediction_accuracy(),
        'total_predictions': len(racing_tracker.prediction_accuracy_history),
        'recent_accuracy': (
            sum(list(racing_tracker.prediction_accuracy_history)[-20:]) / 20
            if len(racing_tracker.prediction_accuracy_history) >= 20 else None
        )
    }
