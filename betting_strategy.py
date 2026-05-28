import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

logger = structlog.get_logger()

class StrategyType(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VALUE_HUNTER = "value_hunter"
    ADAPTIVE = "adaptive"

class BetType(Enum):
    WIN = "win"
    PLACE = "place"
    EXACTA = "exacta"
    TRIFECTA = "trifecta"
    QUINELLA = "quinella"

@dataclass
class BettingRecommendation:
    """Individual betting recommendation."""
    race_id: str
    horse_name: str
    bet_type: BetType
    recommended_stake: float
    max_stake: float
    confidence: float
    overlay_value: float
    expected_value: float
    risk_rating: str  # "LOW", "MEDIUM", "HIGH"
    strategy_used: StrategyType
    reasoning: str

@dataclass
class RaceStrategy:
    """Strategy for an entire race."""
    race_id: str
    total_recommended_outlay: float
    number_of_bets: int
    expected_roi: float
    risk_assessment: str
    recommendations: List[BettingRecommendation]
    strategy_confidence: float

class BettingStrategyEngine:
    """AI-powered betting strategy engine."""
    
    def __init__(self, prediction_tracker):
        self.prediction_tracker = prediction_tracker
        self.bankroll = 1000.0  # Default bankroll
        self.risk_tolerance = "moderate"  # conservative, moderate, aggressive
        self.min_overlay_threshold = 0.15  # Minimum 15% overlay to consider
        self.min_confidence_threshold = 0.6  # Minimum confidence to bet
        
        # Strategy parameters (learned from data)
        self.strategy_parameters = {
            StrategyType.CONSERVATIVE: {
                'min_overlay': 0.25,
                'min_confidence': 0.8,
                'max_stake_percentage': 0.02,  # 2% of bankroll max
                'required_accuracy': 0.3
            },
            StrategyType.MODERATE: {
                'min_overlay': 0.15,
                'min_confidence': 0.65,
                'max_stake_percentage': 0.05,
                'required_accuracy': 0.25
            },
            StrategyType.AGGRESSIVE: {
                'min_overlay': 0.10,
                'min_confidence': 0.5,
                'max_stake_percentage': 0.10,
                'required_accuracy': 0.20
            },
            StrategyType.VALUE_HUNTER: {
                'min_overlay': 0.30,
                'min_confidence': 0.4,
                'max_stake_percentage': 0.08,
                'required_accuracy': 0.15
            }
        }
    
    def set_bankroll(self, amount: float):
        """Set current bankroll amount."""
        self.bankroll = amount
        logger.info("bankroll_updated", new_amount=amount)
    
    def analyze_race_strategy(self, race_prediction) -> RaceStrategy:
        """Analyze a race and provide betting strategy."""
        
        # Get historical performance for similar conditions
        performance_data = self._get_condition_performance(race_prediction)
        
        # Select optimal strategy based on performance
        strategy_type = self._select_strategy(performance_data, race_prediction)
        
        # Generate individual bet recommendations
        recommendations = self._generate_bet_recommendations(race_prediction, strategy_type)
        
        # Calculate race-level metrics
        total_outlay = sum(rec.recommended_stake for rec in recommendations)
        expected_roi = self._calculate_expected_race_roi(recommendations)
        
        race_strategy = RaceStrategy(
            race_id=race_prediction.race_id,
            total_recommended_outlay=total_outlay,
            number_of_bets=len(recommendations),
            expected_roi=expected_roi,
            risk_assessment=self._assess_race_risk(race_prediction, recommendations),
            recommendations=recommendations,
            strategy_confidence=self._calculate_strategy_confidence(performance_data)
        )
        
        logger.info(
            "race_strategy_generated",
            race_id=race_prediction.race_id,
            strategy=strategy_type.value,
            num_bets=len(recommendations),
            total_outlay=total_outlay,
            expected_roi=expected_roi
        )
        
        return race_strategy
    
    def _get_condition_performance(self, race_prediction) -> Dict:
        """Get historical performance for similar race conditions."""
        accuracy_data = self.prediction_tracker.get_accuracy_by_conditions()
        
        # Find matching conditions
        track_performance = accuracy_data.get(f"track_{race_prediction.track}", {})
        type_performance = accuracy_data.get(f"type_{race_prediction.race_type}", {})
        field_size_cat = "small" if race_prediction.field_size <= 8 else "large"
        field_performance = accuracy_data.get(f"field_{field_size_cat}", {})
        
        return {
            'track_accuracy': track_performance.get('accuracy', 0.2),
            'track_roi': track_performance.get('average_roi', 0),
            'track_sample': track_performance.get('sample_size', 0),
            'type_accuracy': type_performance.get('accuracy', 0.2),
            'type_roi': type_performance.get('average_roi', 0),
            'field_accuracy': field_performance.get('accuracy', 0.2),
            'field_roi': field_performance.get('average_roi', 0),
            'overall_accuracy': self.prediction_tracker.get_overall_accuracy().get('win_accuracy', 0.2)
        }
    
    def _select_strategy(self, performance_data: Dict, race_prediction) -> StrategyType:
        """Select optimal strategy based on historical performance."""
        
        # Calculate weighted accuracy score
        track_weight = min(performance_data['track_sample'] / 20, 1.0)  # Cap at 20 samples
        weighted_accuracy = (
            performance_data['track_accuracy'] * track_weight +
            performance_data['type_accuracy'] * 0.3 +
            performance_data['overall_accuracy'] * (1 - track_weight)
        )
        
        # Calculate average ROI
        avg_roi = (performance_data['track_roi'] + performance_data['type_roi']) / 2
        
        # Strategy selection logic
        if weighted_accuracy >= 0.35 and avg_roi > 5:
            return StrategyType.AGGRESSIVE
        elif weighted_accuracy >= 0.25 and avg_roi > 0:
            return StrategyType.MODERATE
        elif weighted_accuracy >= 0.20:
            return StrategyType.CONSERVATIVE
        elif avg_roi > 10:  # High value regardless of accuracy
            return StrategyType.VALUE_HUNTER
        else:
            return StrategyType.CONSERVATIVE  # Play it safe
    
    def _generate_bet_recommendations(self, race_prediction, strategy_type: StrategyType) -> List[BettingRecommendation]:
        """Generate specific betting recommendations for a race."""
        recommendations = []
        strategy_params = self.strategy_parameters[strategy_type]
        
        # Sort horses by overlay value
        value_horses = [
            horse for horse in race_prediction.horses
            if horse.overlay_value >= strategy_params['min_overlay']
            and horse.confidence >= strategy_params['min_confidence']
        ]
        value_horses.sort(key=lambda h: h.overlay_value * h.confidence, reverse=True)
        
        for horse in value_horses[:3]:  # Max 3 bets per race
            # Calculate optimal stake using modified Kelly Criterion
            stake = self._calculate_optimal_stake(
                horse.overlay_value,
                horse.confidence,
                horse.bookmaker_odds,
                strategy_params
            )
            
            if stake > 0:
                recommendation = BettingRecommendation(
                    race_id=race_prediction.race_id,
                    horse_name=horse.horse_name,
                    bet_type=BetType.WIN,  # Start with win bets
                    recommended_stake=stake,
                    max_stake=self.bankroll * strategy_params['max_stake_percentage'],
                    confidence=horse.confidence,
                    overlay_value=horse.overlay_value,
                    expected_value=self._calculate_expected_value(horse, stake),
                    risk_rating=self._assess_bet_risk(horse, stake),
                    strategy_used=strategy_type,
                    reasoning=self._generate_reasoning(horse, strategy_type, stake)
                )
                recommendations.append(recommendation)
        
        # Add combination bets if appropriate
        if len(recommendations) >= 2 and strategy_type in [StrategyType.MODERATE, StrategyType.AGGRESSIVE]:
            combo_rec = self._generate_combination_bet(race_prediction, recommendations, strategy_type)
            if combo_rec:
                recommendations.append(combo_rec)
        
        return recommendations
    
    def _calculate_optimal_stake(self, overlay_value: float, confidence: float, odds: float, strategy_params: Dict) -> float:
        """Calculate optimal stake using modified Kelly Criterion."""
        
        # Convert overlay to win probability advantage
        implied_prob = 1 / odds
        our_prob = implied_prob * (1 + overlay_value)
        
        # Kelly Criterion: f = (bp - q) / b
        # Where: b = odds-1, p = our probability, q = 1-p
        b = odds - 1
        p = our_prob * confidence  # Adjust for confidence
        q = 1 - p
        
        if p <= implied_prob:  # No edge
            return 0.0
        
        # Basic Kelly percentage
        kelly_fraction = (b * p - q) / b
        
        # Apply safety constraints
        max_kelly = 0.25  # Never bet more than 25% Kelly
        kelly_fraction = min(kelly_fraction, max_kelly)
        
        # Apply strategy-specific limits
        max_stake = self.bankroll * strategy_params['max_stake_percentage']
        kelly_stake = self.bankroll * kelly_fraction
        
        # Return the smaller of Kelly or strategy limit
        stake = min(kelly_stake, max_stake)
        
        # Minimum bet threshold
        return stake if stake >= 5.0 else 0.0
    
    def _calculate_expected_value(self, horse, stake: float) -> float:
        """Calculate expected value of a bet."""
        win_prob = (1 / horse.bookmaker_odds) * (1 + horse.overlay_value) * horse.confidence
        loss_prob = 1 - win_prob
        
        expected_return = win_prob * (stake * horse.bookmaker_odds)
        expected_loss = loss_prob * stake
        
        return expected_return - expected_loss - stake
    
    def _assess_bet_risk(self, horse, stake: float) -> str:
        """Assess risk level of individual bet."""
        stake_percentage = stake / self.bankroll
        
        if stake_percentage > 0.05 or horse.confidence < 0.6:
            return "HIGH"
        elif stake_percentage > 0.02 or horse.overlay_value < 0.2:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_combination_bet(self, race_prediction, recommendations: List[BettingRecommendation], strategy_type: StrategyType) -> Optional[BettingRecommendation]:
        """Generate exacta/quinella recommendation if appropriate."""
        if len(recommendations) < 2:
            return None
        
        top_two = recommendations[:2]
        combo_confidence = (top_two[0].confidence + top_two[1].confidence) / 2
        
        if combo_confidence >= 0.7:
            stake = min(
                self.bankroll * 0.01,  # 1% max for combinations
                (top_two[0].recommended_stake + top_two[1].recommended_stake) * 0.3
            )
            
            return BettingRecommendation(
                race_id=race_prediction.race_id,
                horse_name=f"{top_two[0].horse_name} / {top_two[1].horse_name}",
                bet_type=BetType.EXACTA,
                recommended_stake=stake,
                max_stake=stake,
                confidence=combo_confidence,
                overlay_value=min(top_two[0].overlay_value, top_two[1].overlay_value),
                expected_value=stake * 2,  # Rough estimate
                risk_rating="HIGH",
                strategy_used=strategy_type,
                reasoning="High-confidence combination bet"
            )
        
        return None
    
    def _generate_reasoning(self, horse, strategy_type: StrategyType, stake: float) -> str:
        """Generate human-readable reasoning for bet recommendation."""
        reasons = []
        
        if horse.overlay_value > 0.3:
            reasons.append(f"Significant value overlay ({horse.overlay_value:.1%})")
        elif horse.overlay_value > 0.2:
            reasons.append(f"Good value overlay ({horse.overlay_value:.1%})")
        
        if horse.confidence > 0.8:
            reasons.append("Very high model confidence")
        elif horse.confidence > 0.7:
            reasons.append("High model confidence")
        
        if stake > self.bankroll * 0.03:
            reasons.append("Kelly Criterion suggests larger stake")
        
        strategy_reason = {
            StrategyType.CONSERVATIVE: "Conservative approach - only betting strong overlays",
            StrategyType.MODERATE: "Moderate approach - balanced risk/reward",
            StrategyType.AGGRESSIVE: "Aggressive approach - maximizing expected value",
            StrategyType.VALUE_HUNTER: "Value hunting - focusing on large overlays"
        }
        
        reasons.append(strategy_reason.get(strategy_type, ""))
        
        return ". ".join(reasons)
    
    def _calculate_expected_race_roi(self, recommendations: List[BettingRecommendation]) -> float:
        """Calculate expected ROI for entire race strategy."""
        total_stake = sum(rec.recommended_stake for rec in recommendations)
        total_expected_value = sum(rec.expected_value for rec in recommendations)
        
        if total_stake == 0:
            return 0.0
        
        return (total_expected_value / total_stake) * 100
    
    def _assess_race_risk(self, race_prediction, recommendations: List[BettingRecommendation]) -> str:
        """Assess overall risk level for race strategy."""
        total_stake = sum(rec.recommended_stake for rec in recommendations)
        stake_percentage = total_stake / self.bankroll
        
        high_risk_bets = len([rec for rec in recommendations if rec.risk_rating == "HIGH"])
        
        if stake_percentage > 0.15 or high_risk_bets > 1:
            return "HIGH"
        elif stake_percentage > 0.08 or high_risk_bets > 0:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_strategy_confidence(self, performance_data: Dict) -> float:
        """Calculate confidence in strategy selection."""
        sample_size = performance_data.get('track_sample', 0)
        accuracy = performance_data.get('track_accuracy', 0.2)
        
        # Confidence based on sample size and accuracy
        sample_confidence = min(sample_size / 50, 1.0)  # Full confidence at 50+ samples
        accuracy_confidence = min(accuracy / 0.3, 1.0)  # Full confidence at 30%+ accuracy
        
        return (sample_confidence + accuracy_confidence) / 2
    
    def get_bankroll_management_advice(self) -> Dict:
        """Get bankroll management recommendations."""
        recent_performance = self.prediction_tracker.get_recent_performance_trend(days=7)
        
        if recent_performance.get('error'):
            return {"advice": "Insufficient data for bankroll advice"}
        
        recent_roi = recent_performance['trend_summary']['average_daily_roi']
        
        advice = {
            'current_bankroll': self.bankroll,
            'recommended_daily_limit': self.bankroll * 0.05,  # 5% max per day
            'recent_performance': recent_roi,
            'bankroll_trend': 'growing' if recent_roi > 2 else 'stable' if recent_roi > -2 else 'declining',
            'recommendations': []
        }
        
        if recent_roi > 5:
            advice['recommendations'].append("Strong performance - consider slightly increasing bet sizes")
        elif recent_roi < -5:
            advice['recommendations'].append("Poor recent performance - reduce bet sizes temporarily")
        
        if self.bankroll < 500:
            advice['recommendations'].append("Low bankroll - focus on very selective value bets only")
        
        return advice

# Global strategy engine
strategy_engine = None

def initialize_strategy_engine(prediction_tracker):
    """Initialize the strategy engine with prediction tracker."""
    global strategy_engine
    strategy_engine = BettingStrategyEngine(prediction_tracker)
    return strategy_engine
