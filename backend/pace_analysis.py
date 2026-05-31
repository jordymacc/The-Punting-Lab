"""Pace Analysis Engine"""
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class PaceProfile:
    expected_tempo: str
    early_speed_count: int
    midfield_count: int
    backmarker_count: int
    bias: str
    confidence: str
    reasoning: List[str]

@dataclass
class HorsePaceRating:
    horse_name: str
    pace_type: str
    early_speed: float
    sustainability: float
    closing_ability: float
    versatility: float
    pace_suitability_score: float
    reasoning: List[str]

class PaceAnalyzer:
    def __init__(self):
        self.name = "Pace Analyzer"
    
    def analyze_race_pace(self, horses: List[Dict]) -> PaceProfile:
        if not horses:
            return PaceProfile("MODERATE", 0, 0, 0, "BALANCED", "LOW", ["No data"])
        
        reasoning = []
        leaders = []
        midfielders = []
        backmarkers = []
        
        for horse in horses:
            barrier = horse.get("barrier", 0)
            wins = self._parse_pct(horse.get("career_wins", "0"))
            
            if barrier <= 4 and wins >= 20:
                leaders.append(horse)
            elif 4 < barrier <= 10:
                midfielders.append(horse)
            else:
                backmarkers.append(horse)
        
        leader_quality = sum(self._parse_pct(h.get("career_wins", "0")) for h in leaders) / max(len(leaders), 1)
        
        if len(leaders) >= 3 and leader_quality >= 25:
            expected_tempo = "FAST"
            reasoning.append(f"Multiple quality leaders → FAST")
        elif len(leaders) <= 1:
            expected_tempo = "SLOW"
            reasoning.append(f"Few leaders → SLOW")
        else:
            expected_tempo = "MODERATE"
            reasoning.append(f"Balanced → MODERATE")
        
        if expected_tempo == "FAST" and len(leaders) >= 2:
            bias = "LEADERS"
        elif expected_tempo == "SLOW" and len(backmarkers) >= 3:
            bias = "CLOSERS"
        else:
            bias = "BALANCED"
        
        return PaceProfile(
            expected_tempo=expected_tempo,
            early_speed_count=len(leaders),
            midfield_count=len(midfielders),
            backmarker_count=len(backmarkers),
            bias=bias,
            confidence="HIGH" if len(leaders) >= 2 else "MEDIUM" if len(leaders) >= 1 else "LOW",
            reasoning=reasoning
        )
    
    def analyze_horse_pace(self, horse: Dict, race_pace: PaceProfile) -> HorsePaceRating:
        name = horse.get("horse_name", "Unknown")
        barrier = horse.get("barrier", 0)
        form = horse.get("form_string", "")
        wins = self._parse_pct(horse.get("career_wins", "0"))
        track_wins = self._parse_pct(horse.get("track_wins", "0"))
        
        reasoning = []
        
        if barrier <= 4 and wins >= 20:
            pace_type = "LEADER"
            early_speed = 85.0
            sustainability = 70.0
            closing_ability = 50.0
        elif 4 < barrier <= 8 and wins >= 15:
            pace_type = "MIDFIELD"
            early_speed = 65.0
            sustainability = 75.0
            closing_ability = 70.0
        elif barrier > 8 or wins < 15:
            pace_type = "BACKMARKER"
            early_speed = 40.0
            sustainability = 60.0
            closing_ability = 85.0
        else:
            pace_type = "VERSATILE"
            early_speed = 60.0
            sustainability = 70.0
            closing_ability = 70.0
        
        suitability = 50.0
        
        if race_pace.bias == "LEADERS":
            if pace_type == "LEADER":
                suitability = 90.0
                reasoning.append("✅ Leader in fast-pace race")
            elif pace_type == "MIDFIELD":
                suitability = 60.0
                reasoning.append("⚠️ Midfielders struggle in fast pace")
            else:
                suitability = 30.0
                reasoning.append("❌ Backmarker in leader race")
        elif race_pace.bias == "CLOSERS":
            if pace_type == "BACKMARKER":
                suitability = 90.0
                reasoning.append("✅ Closer in slow-pace race")
            elif pace_type == "MIDFIELD":
                suitability = 65.0
                reasoning.append("⚠️ Okay in slow races")
            else:
                suitability = 40.0
                reasoning.append("❌ Leader may tire")
        else:
            if pace_type == "VERSATILE":
                suitability = 80.0
                reasoning.append("✅ Versatile in balanced race")
            elif pace_type == "MIDFIELD":
                suitability = 75.0
                reasoning.append("✅ Midfielders excel in balanced")
            else:
                suitability = 65.0
                reasoning.append("⚠️ Specialist in balanced race")
        
        versatility = 50.0
        if pace_type == "VERSATILE":
            versatility = 85.0
            suitability += 10
        
        if track_wins >= 30:
            suitability += 15
            reasoning.append(f"Strong track record ({track_wins:.0f}%)")
        
        suitability = min(suitability, 100.0)
        
        return HorsePaceRating(
            horse_name=name,
            pace_type=pace_type,
            early_speed=min(early_speed, 100.0),
            sustainability=min(sustainability, 100.0),
            closing_ability=min(closing_ability, 100.0),
            versatility=versatility,
            pace_suitability_score=suitability,
            reasoning=reasoning
        )
    
    def _parse_pct(self, val) -> float:
        if isinstance(val, (int, float)):
            return float(val) * 100 if float(val) <= 1.0 else float(val)
        if isinstance(val, str):
            try:
                v = float(val.replace("%", "").strip())
                return v * 100 if v <= 1.0 else v
            except:
                return 0.0
        return 0.0

pace_analyzer = PaceAnalyzer()
__all__ = ["PaceAnalyzer", "pace_analyzer", "PaceProfile", "HorsePaceRating"]
