# Add this to your main.py imports
from betting_strategy import initialize_strategy_engine, strategy_engine, StrategyType
from prediction_tracker import prediction_tracker

# Initialize strategy engine on startup
@app.on_event("startup")
async def startup_event():
    global strategy_engine
    strategy_engine = initialize_strategy_engine(prediction_tracker)

@app.post("/strategy/analyze-race")
async def analyze_race_strategy(race_data: dict):
    """Get betting strategy for a specific race."""
    try:
        # Convert race_data to prediction format (you may need to adapt this)
        # This assumes race_data matches your RacePrediction structure
        from prediction_tracker import RacePrediction, HorsePrediction
        
        horses = [HorsePrediction(**horse) for horse in race_data.get('horses', [])]
        race_pred = RacePrediction(
            race_id=race_data['race_id'],
            track=race_data['track'],
            race_time=datetime.fromisoformat(race_data['race_time']),
            race_type=race_data.get('race_type', 'unknown'),
            distance=race_data.get('distance', 0),
            surface=race_data.get('surface', 'unknown'),
            weather=race_data.get('weather', 'unknown'),
            field_size=race_data.get('field_size', len(horses)),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data['predicted_winner'],
            predicted_quinella=race_data.get('predicted_quinella', []),
            predicted_trifecta=race_data.get('predicted_trifecta', [])
        )
        
        strategy = strategy_engine.analyze_race_strategy(race_pred)
        return asdict(strategy)
        
    except Exception as e:
        logger.error("strategy_analysis_failed", error=str(e))
        return {"error": str(e)}

@app.get("/strategy/bankroll-advice")
async def get_bankroll_advice():
    """Get bankroll management advice."""
    return strategy_engine.get_bankroll_management_advice()

@app.post("/strategy/set-bankroll")
async def set_bankroll(data: dict):
    """Set current bankroll amount."""
    try:
        amount = data.get('amount')
        if amount and amount > 0:
            strategy_engine.set_bankroll(amount)
            return {"success": True, "new_bankroll": amount}
        else:
            return {"error": "Invalid bankroll amount"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/strategy/performance-summary")
async def get_strategy_performance():
    """Get performance summary for all strategies."""
    # This would require tracking which strategy was used for each bet
    # For now, return general performance metrics
    overall = prediction_tracker.get_overall_accuracy()
    conditions = prediction_tracker.get_accuracy_by_conditions()
    
    return {
        "overall_performance": overall,
        "performance_by_conditions": conditions,
        "strategy_recommendations": {
            "conservative_situations": "When track accuracy < 20%",
            "aggressive_situations": "When track accuracy > 30% and ROI > 5%",
            "value_hunting_situations": "When overlays > 30% regardless of accuracy"
        }
    }
