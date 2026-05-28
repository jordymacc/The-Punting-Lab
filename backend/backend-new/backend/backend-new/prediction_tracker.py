import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import statistics
import structlog

logger = structlog.get_logger()

@dataclass
class HorsePrediction:
    """Individual horse prediction data."""
    horse_name: str
    predicted_odds: float
    bookmaker_odds: float
    overlay_value: float  # How much value we think there is
    confidence: float  # 0-1, how confident we are
    predicted_finish: int  # 1=win, 2=place, etc.
    actual_finish: Optional[int] = None
    
@dataclass
class RacePrediction:
    """Complete race prediction data."""
    race_id: str
    track: str
    race_time: datetime
    race_type: str  # "maiden", "handicap", "stakes", etc.
    distance: int
    surface: str  # "turf", "dirt"
    weather: str
    field_size: int
    prediction_time: datetime
    horses: List[HorsePrediction]
    predicted_winner: str
    predicted_quinella: List[str]  # Top 2
    predicted_trifecta: List[str]  # Top 3
    
    # Results (filled in after race)
    actual_winner: Optional[str] = None
    actual_quinella: Optional[List[str]] = None
    actual_trifecta: Optional[List[str]] = None
    winning_dividend: Optional[float] = None
    place_dividends: Optional[Dict[str, float]] = None
    
    # Analysis results
    win_prediction_correct: Optional[bool] = None
    place_predictions_correct: Optional[int] = None  # How many we got right
    overlay_roi: Optional[float] = None  # Return if betting overlays
    model_performance_score: Optional[float] = None

class PredictionAccuracyTracker:
    """Tracks prediction accuracy and analyzes performance."""
    
    def __init__(self):
        self.predictions: Dict[str, RacePrediction] = {}
        self.completed_predictions: List[RacePrediction] = []
        self.accuracy_history = deque(maxlen=1000)  # Last 1000 races
        self.roi_history = deque(maxlen=500)  # ROI tracking
        
    def record_prediction(self, race_prediction: RacePrediction):
        """Record a new race prediction."""
        self.predictions[race_prediction.race_id] = race_prediction
        
        logger.info(
            "prediction_recorded",
            race_id=race_prediction.race_id,
            track=race_prediction.track,
            predicted_winner=race_prediction.predicted_winner,
            num_overlays=len([h for h in race_prediction.horses if h.overlay_value > 0]),
            avg_confidence=sum(h.confidence for h in race_prediction.horses) / len(race_prediction.horses)
        )
    
    def record_race_result(self, race_id: str, results: Dict):
        """Record actual race results and calculate accuracy."""
        if race_id not in self.predictions:
            logger.warning("race_result_no_prediction", race_id=race_id)
            return
        
        prediction = self.predictions[race_id]
        
        # Extract results
        prediction.actual_winner = results.get('winner')
        prediction.actual_quinella = results.get('quinella', [])
        prediction.actual_trifecta = results.get('trifecta', [])
        prediction.winning_dividend = results.get('win_dividend')
        prediction.place_dividends = results.get('place_dividends', {})
        
        # Update horse finish positions
        finishing_order = results.get('finishing_order', [])
        for horse in prediction.horses:
            if horse.horse_name in finishing_order:
                horse.actual_finish = finishing_order.index(horse.horse_name) + 1
        
        # Analyze prediction accuracy
        self._analyze_prediction_accuracy(prediction)
        
        # Move to completed predictions
        self.completed_predictions.append(prediction)
        self.accuracy_history.append(prediction.win_prediction_correct)
        if prediction.overlay_roi is not None:
            self.roi_history.append(prediction.overlay_roi)
        
        del self.predictions[race_id]
        
        logger.info(
            "race_result_analyzed",
            race_id=race_id,
            win_correct=prediction.win_prediction_correct,
            place_correct=prediction.place_predictions_correct,
            overlay_roi=prediction.overlay_roi,
            performance_score=prediction.model_performance_score
        )
    
    def _analyze_prediction_accuracy(self, prediction: RacePrediction):
        """Analyze how accurate our prediction was."""
        
        # Win prediction accuracy
        prediction.win_prediction_correct = (
            prediction.predicted_winner == prediction.actual_winner
        )
        
        # Place prediction accuracy (top 2)
        if prediction.actual_quinella:
            correct_places = len(set(prediction.predicted_quinella[:2]) & set(prediction.actual_quinella))
            prediction.place_predictions_correct = correct_places
        
        # Calculate overlay ROI
        prediction.overlay_roi = self._calculate_overlay_roi(prediction)
        
        # Overall model performance score (weighted metric)
        prediction.model_performance_score = self._calculate_performance_score(prediction)
    
    def _calculate_overlay_roi(self, prediction: RacePrediction) -> float:
        """Calculate ROI if we bet $1 on each overlay."""
        total_bet = 0
        total_return = 0
        
        for horse in prediction.horses:
            if horse.overlay_value > 0.1:  # Only bet on significant overlays
                bet_amount = horse.overlay_value  # Bet amount proportional to overlay
                total_bet += bet_amount
                
                if horse.horse_name == prediction.actual_winner:
                    # Horse won - calculate return
                    if prediction.winning_dividend:
                        total_return += bet_amount * (prediction.winning_dividend / 100)  # Convert to decimal odds
                elif horse.actual_finish and horse.actual_finish <= 3:  # Placed
                    # Horse placed - get place dividend
                    place_div = prediction.place_dividends.get(horse.horse_name)
                    if place_div:
                        total_return += bet_amount * (place_div / 100)
        
        if total_bet == 0:
            return 0.0
        
        roi = ((total_return - total_bet) / total_bet) * 100
        return roi
    
    def _calculate_performance_score(self, prediction: RacePrediction) -> float:
        """Calculate weighted performance score (0-100)."""
        score = 0.0
        
        # Win prediction (40% weight)
        if prediction.win_prediction_correct:
            score += 40.0
        
        # Place predictions (30% weight) 
        if prediction.place_predictions_correct is not None:
            place_score = (prediction.place_predictions_correct / 2) * 30.0
            score += place_score
        
        # Overlay ROI (30% weight)
        if prediction.overlay_roi is not None:
            # Positive ROI gets full points, scaled
            roi_score = min(30.0, max(0.0, prediction.overlay_roi / 10 * 30))
            score += roi_score
        
        return score
    
    def get_overall_accuracy(self) -> Dict:
        """Get overall prediction accuracy metrics."""
        if not self.completed_predictions:
            return {"error": "No completed predictions yet"}
        
        total_races = len(self.completed_predictions)
        win_correct = sum(1 for p in self.completed_predictions if p.win_prediction_correct)
        
        # Calculate place accuracy
        place_predictions = [p for p in self.completed_predictions if p.place_predictions_correct is not None]
        avg_place_accuracy = (
            sum(p.place_predictions_correct for p in place_predictions) / len(place_predictions) / 2
            if place_predictions else 0
        )
        
        # Calculate ROI
        profitable_predictions = [p for p in self.completed_predictions if p.overlay_roi is not None]
        avg_roi = (
            sum(p.overlay_roi for p in profitable_predictions) / len(profitable_predictions)
            if profitable_predictions else 0
        )
        
        return {
            'total_predictions': total_races,
            'win_accuracy': win_correct / total_races,
            'place_accuracy': avg_place_accuracy,
            'average_roi': avg_roi,
            'profitable_rate': len([p for p in profitable_predictions if p.overlay_roi > 0]) / len(profitable_predictions) if profitable_predictions else 0,
            'average_performance_score': sum(p.model_performance_score for p in self.completed_predictions if p.model_performance_score) / total_races
        }
    
    def get_accuracy_by_conditions(self) -> Dict:
        """Analyze accuracy by race conditions."""
        analysis = defaultdict(lambda: {'total': 0, 'correct': 0, 'roi': []})
        
        for pred in self.completed_predictions:
            # By track
            key = f"track_{pred.track}"
            analysis[key]['total'] += 1
            if pred.win_prediction_correct:
                analysis[key]['correct'] += 1
            if pred.overlay_roi is not None:
                analysis[key]['roi'].append(pred.overlay_roi)
            
            # By race type
            key = f"type_{pred.race_type}"
            analysis[key]['total'] += 1
            if pred.win_prediction_correct:
                analysis[key]['correct'] += 1
            if pred.overlay_roi is not None:
                analysis[key]['roi'].append(pred.overlay_roi)
            
            # By field size
            field_category = "small" if pred.field_size <= 8 else "large"
            key = f"field_{field_category}"
            analysis[key]['total'] += 1
            if pred.win_prediction_correct:
                analysis[key]['correct'] += 1
            if pred.overlay_roi is not None:
                analysis[key]['roi'].append(pred.overlay_roi)
        
        # Convert to percentages and averages
        results = {}
        for condition, data in analysis.items():
            if data['total'] > 0:
                results[condition] = {
                    'accuracy': data['correct'] / data['total'],
                    'sample_size': data['total'],
                    'average_roi': sum(data['roi']) / len(data['roi']) if data['roi'] else 0
                }
        
        return results
    
    def get_confidence_analysis(self) -> Dict:
        """Analyze relationship between confidence and accuracy."""
        confidence_buckets = defaultdict(lambda: {'predictions': [], 'accuracies': []})
        
        for pred in self.completed_predictions:
            for horse in pred.horses:
                if horse.actual_finish is not None:
                    # Bucket by confidence level
                    confidence_level = round(horse.confidence * 10) / 10  # Round to nearest 0.1
                    bucket_key = f"{confidence_level:.1f}"
                    
                    confidence_buckets[bucket_key]['predictions'].append(horse.predicted_finish)
                    confidence_buckets[bucket_key]['accuracies'].append(
                        horse.predicted_finish == horse.actual_finish
                    )
        
        results = {}
        for conf_level, data in confidence_buckets.items():
            if len(data['accuracies']) >= 5:  # Minimum sample size
                results[conf_level] = {
                    'accuracy': sum(data['accuracies']) / len(data['accuracies']),
                    'sample_size': len(data['accuracies']),
                    'confidence_level': float(conf_level)
                }
        
        return results
    
    def get_recent_performance_trend(self, days: int = 30) -> Dict:
        """Get performance trend over recent days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_predictions = [
            p for p in self.completed_predictions 
            if p.prediction_time >= cutoff_date
        ]
        
        if not recent_predictions:
            return {"error": f"No predictions in last {days} days"}
        
        # Group by day
        daily_performance = defaultdict(lambda: {'correct': 0, 'total': 0, 'roi': []})
        
        for pred in recent_predictions:
            day_key = pred.prediction_time.strftime('%Y-%m-%d')
            daily_performance[day_key]['total'] += 1
            if pred.win_prediction_correct:
                daily_performance[day_key]['correct'] += 1
            if pred.overlay_roi is not None:
                daily_performance[day_key]['roi'].append(pred.overlay_roi)
        
        # Calculate trends
        trend_data = []
        for day, data in sorted(daily_performance.items()):
            accuracy = data['correct'] / data['total'] if data['total'] > 0 else 0
            avg_roi = sum(data['roi']) / len(data['roi']) if data['roi'] else 0
            
            trend_data.append({
                'date': day,
                'accuracy': accuracy,
                'roi': avg_roi,
                'predictions': data['total']
            })
        
        return {
            'daily_performance': trend_data,
            'trend_summary': {
                'total_predictions': len(recent_predictions),
                'average_daily_accuracy': sum(d['accuracy'] for d in trend_data) / len(trend_data),
                'average_daily_roi': sum(d['roi'] for d in trend_data) / len(trend_data)
            }
        }

# Global tracker instance
prediction_tracker = PredictionAccuracyTracker()
