# Add this to your main.py imports
from prediction_tracker import prediction_tracker, RacePrediction, HorsePrediction

@app.get("/predictions/accuracy")
async def get_prediction_accuracy():
    """Get overall prediction accuracy metrics."""
    return prediction_tracker.get_overall_accuracy()

@app.get("/predictions/analysis")
async def get_prediction_analysis():
    """Get detailed prediction analysis."""
    return {
        'overall': prediction_tracker.get_overall_accuracy(),
        'by_conditions': prediction_tracker.get_accuracy_by_conditions(),
        'confidence_analysis': prediction_tracker.get_confidence_analysis(),
        'recent_trend': prediction_tracker.get_recent_performance_trend(days=14)
    }

@app.get("/predictions/performance/{days}")
async def get_recent_performance(days: int):
    """Get performance trend for specified number of days."""
    return prediction_tracker.get_recent_performance_trend(days)

@app.post("/predictions/record")
async def record_prediction(race_data: dict):
    """Record a new race prediction."""
    try:
        # Convert dict to RacePrediction object
        horses = [
            HorsePrediction(**horse) for horse in race_data.get('horses', [])
        ]
        
        race_pred = RacePrediction(
            race_id=race_data['race_id'],
            track=race_data['track'],
            race_time=datetime.fromisoformat(race_data['race_time']),
            race_type=race_data.get('race_type', 'unknown'),
            distance=race_data.get('distance', 0),
            surface=race_data.get('surface', 'unknown'),
            weather=race_data.get('weather', 'unknown'),
            field_size=race_data.get('field_size', 0),
            prediction_time=datetime.now(),
            horses=horses,
            predicted_winner=race_data['predicted_winner'],
            predicted_quinella=race_data.get('predicted_quinella', []),
            predicted_trifecta=race_data.get('predicted_trifecta', [])
        )
        
        prediction_tracker.record_prediction(race_pred)
        return {"success": True, "race_id": race_data['race_id']}
        
    except Exception as e:
        logger.error("failed_to_record_prediction", error=str(e), race_data=race_data)
        return {"success": False, "error": str(e)}

@app.post("/predictions/result")
async def record_race_result(result_data: dict):
    """Record actual race results."""
    try:
        prediction_tracker.record_race_result(
            race_id=result_data['race_id'],
            results=result_data['results']
        )
        return {"success": True, "race_id": result_data['race_id']}
        
    except Exception as e:
        logger.error("failed_to_record_result", error=str(e), result_data=result_data)
        return {"success": False, "error": str(e)}
