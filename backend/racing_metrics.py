import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import asyncio
import structlog

logger = structlog.get_logger()

@dataclass
class RaceMetrics:
    """Metrics for individual race tracking."""
    race_id: str
    track: str
    race_time: datetime
    data_first_seen: datetime
    last_update: datetime
    overlay_generated: bool
    overlay_generation_time: Optional[float]
    prediction_confidence: Optional[float]
    actual_result: Optional[str]
    prediction_accuracy: Optional[bool]

@dataclass
class ScrapingMetrics:
    """Metrics for data source scraping."""
    source: str
    last_successful_scrape: datetime
    last_failed_scrape: Optional[datetime]
    success_count_24h: int
    failure_count_24h: int
    average_response_time: float
    data_quality_score: float

class RacingPerformanceTracker:
    """Tracks racing-specific performance metrics."""
    
    def __init__(self):
        self.race_metrics: Dict[str, RaceMetrics] = {}
        self.scraping_metrics: Dict[str, ScrapingMetrics] = {}
        self.response_times = defaultdict(lambda: deque(maxlen=100))  # Last 100 requests per endpoint
        self.overlay_generation_times = deque(maxlen=50)  # Last 50 overlay generations
        self.websocket_latencies = deque(maxlen=100)
        self.prediction_accuracy_history = deque(maxlen=200)  # Last 200 predictions
        
    def track_scraping_operation(self, source: str, success: bool, response_time: float, data_quality: float = 1.0):
        """Track a scraping operation."""
        now = datetime.now()
        
        if source not in self.scraping_metrics:
            self.scraping_metrics[source] = ScrapingMetrics(
                source=source,
                last_successful_scrape=now if success else datetime.min,
                last_failed_scrape=None if success else now,
                success_count_24h=0,
                failure_count_24h=0,
                average_response_time=response_time,
                data_quality_score=data_quality
            )
        
        metrics = self.scraping_metrics[source]
        
        # Update success/failure counts (last 24h)
        if success:
            metrics.last_successful_scrape = now
            metrics.success_count_24h += 1
        else:
            metrics.last_failed_scrape = now
            metrics.failure_count_24h += 1
        
        # Update average response time (rolling average)
        metrics.average_response_time = (metrics.average_response_time * 0.9) + (response_time * 0.1)
        metrics.data_quality_score = (metrics.data_quality_score * 0.9) + (data_quality * 0.1)
        
        logger.info(
            "scraping_tracked",
            source=source,
            success=success,
            response_time=response_time,
            success_rate_24h=self.get_scraping_success_rate(source)
        )
    
    def track_race_discovery(self, race_id: str, track: str, race_time: datetime):
        """Track when a new race is discovered."""
        if race_id not in self.race_metrics:
            self.race_metrics[race_id] = RaceMetrics(
                race_id=race_id,
                track=track,
                race_time=race_time,
                data_first_seen=datetime.now(),
                last_update=datetime.now(),
                overlay_generated=False,
                overlay_generation_time=None,
                prediction_confidence=None,
                actual_result=None,
                prediction_accuracy=None
            )
            
            logger.info(
                "race_discovered",
                race_id=race_id,
                track=track,
                race_time=race_time.isoformat(),
                time_until_race=str(race_time - datetime.now())
            )
    
    def track_overlay_generation(self, race_id: str, generation_time: float, confidence: float):
        """Track overlay generation for a race."""
        if race_id in self.race_metrics:
            self.race_metrics[race_id].overlay_generated = True
            self.race_metrics[race_id].overlay_generation_time = generation_time
            self.race_metrics[race_id].prediction_confidence = confidence
            self.overlay_generation_times.append(generation_time)
            
            logger.info(
                "overlay_generated",
                race_id=race_id,
                generation_time=generation_time,
                confidence=confidence,
                avg_generation_time=self.get_average_overlay_generation_time()
            )
    
    def track_race_result(self, race_id: str, actual_winner: str, predicted_winner: str = None):
        """Track the actual race result vs prediction."""
        if race_id in self.race_metrics:
            metrics = self.race_metrics[race_id]
            metrics.actual_result = actual_winner
            
            if predicted_winner:
                accuracy = actual_winner == predicted_winner
                metrics.prediction_accuracy = accuracy
                self.prediction_accuracy_history.append(accuracy)
                
                logger.info(
                    "race_result_tracked",
                    race_id=race_id,
                    actual_winner=actual_winner,
                    predicted_winner=predicted_winner,
                    accurate=accuracy,
                    overall_accuracy=self.get_prediction_accuracy()
                )
    
    def track_api_response_time(self, endpoint: str, response_time: float):
        """Track API endpoint response times."""
        self.response_times[endpoint].append(response_time)
        
        if len(self.response_times[endpoint]) % 10 == 0:  # Log every 10 requests
            avg_time = sum(self.response_times[endpoint]) / len(self.response_times[endpoint])
            logger.debug(
                "api_performance",
                endpoint=endpoint,
                avg_response_time=avg_time,
                last_response_time=response_time
            )
    
    def track_websocket_latency(self, latency_ms: float):
        """Track WebSocket message latency."""
        self.websocket_latencies.append(latency_ms)
    
    def get_scraping_success_rate(self, source: str) -> float:
        """Get 24h success rate for a scraping source."""
        if source not in self.scraping_metrics:
            return 0.0
        
        metrics = self.scraping_metrics[source]
        total = metrics.success_count_24h + metrics.failure_count_24h
        if total == 0:
            return 0.0
        
        return metrics.success_count_24h / total
    
    def get_data_freshness(self, source: str) -> Optional[float]:
        """Get data freshness in seconds for a source."""
        if source not in self.scraping_metrics:
            return None
        
        last_update = self.scraping_metrics[source].last_successful_scrape
        if last_update == datetime.min:
            return None
        
        return (datetime.now() - last_update).total_seconds()
    
    def get_average_overlay_generation_time(self) -> float:
        """Get average overlay generation time."""
        if not self.overlay_generation_times:
            return 0.0
        return sum(self.overlay_generation_times) / len(self.overlay_generation_times)
    
    def get_prediction_accuracy(self) -> float:
        """Get overall prediction accuracy rate."""
        if not self.prediction_accuracy_history:
            return 0.0
        return sum(self.prediction_accuracy_history) / len(self.prediction_accuracy_history)
    
    def get_average_websocket_latency(self) -> float:
        """Get average WebSocket latency."""
        if not self.websocket_latencies:
            return 0.0
        return sum(self.websocket_latencies) / len(self.websocket_latencies)
    
    def get_races_by_status(self) -> Dict[str, int]:
        """Get count of races by various statuses."""
        now = datetime.now()
        counts = {
            'upcoming': 0,
            'live': 0,
            'completed': 0,
            'with_overlays': 0,
            'with_results': 0
        }
        
        for race in self.race_metrics.values():
            if race.race_time > now + timedelta(minutes=5):
                counts['upcoming'] += 1
            elif race.race_time > now - timedelta(minutes=5):
                counts['live'] += 1
            else:
                counts['completed'] += 1
            
            if race.overlay_generated:
                counts['with_overlays'] += 1
            
            if race.actual_result:
                counts['with_results'] += 1
        
        return counts
    
    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary."""
        return {
            'timestamp': datetime.now().isoformat(),
            'scraping': {
                source: {
                    'success_rate': self.get_scraping_success_rate(source),
                    'data_freshness_seconds': self.get_data_freshness(source),
                    'average_response_time': metrics.average_response_time,
                    'data_quality_score': metrics.data_quality_score
                }
                for source, metrics in self.scraping_metrics.items()
            },
            'overlays': {
                'average_generation_time': self.get_average_overlay_generation_time(),
                'total_generated': len(self.overlay_generation_times),
                'prediction_accuracy': self.get_prediction_accuracy(),
                'total_predictions': len(self.prediction_accuracy_history)
            },
            'races': self.get_races_by_status(),
            'websockets': {
                'average_latency_ms': self.get_average_websocket_latency(),
                'total_messages': len(self.websocket_latencies)
            },
            'api_performance': {
                endpoint: {
                    'average_response_time': sum(times) / len(times) if times else 0,
                    'total_requests': len(times)
                }
                for endpoint, times in self.response_times.items()
            }
        }

# Global tracker instance
racing_tracker = RacingPerformanceTracker()
