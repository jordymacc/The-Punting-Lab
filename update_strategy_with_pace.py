"""
Update strategy_v3.py to include pace analysis
"""

# Read the current strategy file
with open("strategy_v3.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import at the top (after other imports)
import_section = 'from fastapi.responses import HTMLResponse\nfrom datetime import datetime'
new_import = import_section + '\nfrom pace_analysis import pace_analyzer'

content = content.replace(import_section, new_import)

# Find the FactorAnalyzer class and add pace analysis
# Add this factor to the factors list in analyze_horse method

# Find "# Factor 10: Class Fit" and add pace before it
pace_factor_code = '''    
    def analyze_pace_fit(self, horse: dict, race_horses: list) -> FactorScore:
        """
        FACTOR 10 (moved to 11): Pace Suitability Analysis
        Does the horse suit the expected race tempo?
        """
        from pace_analysis import pace_analyzer
        
        # Analyze race pace
        race_pace = pace_analyzer.analyze_race_pace(race_horses)
        
        # Get horse pace suitability
        score, reasons = pace_analyzer.get_pace_factor_score(horse, race_pace)
        
        if score >= 0.9:
            rating = "EXCELLENT"
            emoji = "🏇"
            details = f"Excellent pace fit - {race_pace.bias} bias race"
        elif score >= 0.7:
            rating = "GOOD"
            emoji = "✅"
            details = f"Good pace fit - suits {race_pace.expected_tempo} tempo"
        elif score >= 0.5:
            rating = "AVERAGE"
            emoji = "📊"
            details = f"Moderate pace fit - {race_pace.bias} bias"
        elif score >= 0.3:
            rating = "POOR"
            emoji = "⚠️"
            details = f"Poor pace fit - doesn't suit {race_pace.expected_tempo} tempo"
        else:
            rating = "AVOID"
            emoji = "❌"
            details = f"Very poor pace fit - {race_pace.bias} bias disadvantages this horse"
        
        weight = 0.12  # 12% weight
        return FactorScore(
            factor_name="Pace Fit",
            score=score,
            weight=weight,
            weighted_score=score * weight,
            rating=rating,
            details=details,
            emoji=emoji
        )
'''

# Update weights to include pace (redistribute to 11 factors)
old_weights = """    WEIGHTS = {
        "overlay_value": 0.18,
        "track_form": 0.12,
        "distance_form": 0.10,
        "recent_form": 0.14,
        "condition_form": 0.10,
        "career_consistency": 0.08,
        "jockey_trainer": 0.08,
        "weight_suitability": 0.06,
        "barrier_position": 0.06,
        "class_fit": 0.08,
    }"""

new_weights = """    WEIGHTS = {
        "overlay_value": 0.16,
        "track_form": 0.11,
        "distance_form": 0.09,
        "recent_form": 0.13,
        "condition_form": 0.09,
        "career_consistency": 0.07,
        "jockey_trainer": 0.07,
        "weight_suitability": 0.05,
        "barrier_position": 0.05,
        "pace_fit": 0.12,  # NEW: Pace analysis
        "class_fit": 0.07,
    }"""

content = content.replace(old_weights, new_weights)

# Write back
with open("strategy_v3.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated strategy_v3.py with pace analysis")
print("")
print("Note: Manually add the analyze_pace_fit method to FactorAnalyzer class")
print("Add it before analyze_class_fit method")
