from dataclasses import dataclass, field
from typing import Optional

@dataclass
class HorseData:
    horse_name: str
    barrier: int
    jockey: str
    trainer: str
    weight: float
    tote_odds: float
    fixed_odds: float
    days_since_last_run: Optional[int] = None
    last_finish: Optional[int] = None
    track_condition: Optional[str] = None
    distance: Optional[str] = None
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    # FormFav real stats
    win_percent: float = 0.0
    place_percent: float = 0.0
    track_win_percent: float = 0.0
    distance_win_percent: float = 0.0
    condition_win_percent: float = 0.0
    career_starts: int = 0
    form_string: str = ""

def calculate_fair_value(horse: HorseData, num_runners: int = 8) -> float:
    # Base: equal share of field
    base = 1.0 / max(num_runners, 1)

    # If we have real career win % from FormFav, use it as primary signal
    if horse.career_starts >= 3 and horse.win_percent > 0:
        # Blend career win% with base (weight career more as starts increase)
        trust = min(horse.career_starts / 20.0, 1.0)
        base = (horse.win_percent * trust) + (base * (1.0 - trust))

    mult = 1.0

    # Track record bonus
    if horse.track_win_percent > 0:
        if horse.track_win_percent >= 0.40:
            mult *= 1.20
        elif horse.track_win_percent >= 0.25:
            mult *= 1.10
        elif horse.track_win_percent >= 0.15:
            mult *= 1.04

    # Distance record bonus
    if horse.distance_win_percent > 0:
        if horse.distance_win_percent >= 0.40:
            mult *= 1.15
        elif horse.distance_win_percent >= 0.25:
            mult *= 1.08
        elif horse.distance_win_percent >= 0.15:
            mult *= 1.03

    # Condition record bonus
    if horse.condition_win_percent > 0:
        if horse.condition_win_percent >= 0.40:
            mult *= 1.12
        elif horse.condition_win_percent >= 0.25:
            mult *= 1.06

    # Recent form from form string
    last_finish = horse.last_finish
    if last_finish is not None:
        if last_finish == 1:
            mult *= 1.18
        elif last_finish == 2:
            mult *= 1.10
        elif last_finish <= 4:
            mult *= 1.04
        elif last_finish >= 8:
            mult *= 0.86

    # Barrier bias
    if horse.barrier <= 3:
        mult *= 1.08
    elif horse.barrier <= 6:
        mult *= 1.02
    elif horse.barrier >= 10:
        mult *= 0.93

    # Weight
    if horse.weight > 58.5:
        mult *= 0.94
    elif horse.weight < 54:
        mult *= 1.06

    # Days since last run
    if horse.days_since_last_run is not None:
        if horse.days_since_last_run > 60:
            mult *= 0.91
        elif horse.days_since_last_run < 14:
            mult *= 1.04

    # Track condition
    condition = (horse.track_condition or "").lower()
    if "heavy" in condition:
        mult *= 0.95
    elif "soft" in condition:
        mult *= 0.97
    elif "good" in condition:
        mult *= 1.03

    # Weather impact
    if horse.wind_speed and horse.wind_speed > 30:
        mult *= 0.97
    if horse.temperature and horse.temperature > 35:
        mult *= 0.95

    fair_prob = base * mult
    return round(min(fair_prob, 0.95), 4)

def calculate_overlay(horse: HorseData, num_runners: int = 8) -> dict:
    fair_prob = calculate_fair_value(horse, num_runners)

    # If no odds available (FormFav free tier), use fair value only
    if horse.tote_odds <= 0:
        # Estimate implied odds from fair prob for display
        est_odds = round((1 / fair_prob) - 1, 2) if fair_prob > 0 else 99.0
        return {
            "horse_name": horse.horse_name,
            "barrier": horse.barrier,
            "jockey": horse.jockey,
            "trainer": horse.trainer,
            "tote_odds": None,
            "fixed_odds": None,
            "fair_value": round(fair_prob * 100, 2),
            "tote_implied": None,
            "overlay_score": 0.0,
            "is_overlay": False,
            "rating": "N/A",
            "est_fair_odds": est_odds,
            "form_string": horse.form_string,
            "career_wins": f"{int(horse.win_percent * 100)}%",
            "track_wins": f"{int(horse.track_win_percent * 100)}%",
            "dist_wins": f"{int(horse.distance_win_percent * 100)}%",
        }

    tote_implied = 1 / (horse.tote_odds + 1)
    overlay_score = round((fair_prob - tote_implied) * 100, 2)
    is_overlay = overlay_score > 2.0

    return {
        "horse_name": horse.horse_name,
        "barrier": horse.barrier,
        "jockey": horse.jockey,
        "trainer": horse.trainer,
        "tote_odds": horse.tote_odds,
        "fixed_odds": horse.fixed_odds,
        "fair_value": round(fair_prob * 100, 2),
        "tote_implied": round(tote_implied * 100, 2),
        "overlay_score": overlay_score,
        "is_overlay": is_overlay,
        "rating": rate_overlay(overlay_score),
        "est_fair_odds": round((1 / fair_prob) - 1, 2) if fair_prob > 0 else 99.0,
        "form_string": horse.form_string,
        "career_wins": f"{int(horse.win_percent * 100)}%",
        "track_wins": f"{int(horse.track_win_percent * 100)}%",
        "dist_wins": f"{int(horse.distance_win_percent * 100)}%",
    }

def rate_overlay(score: float) -> str:
    if score >= 10:
        return "STRONG"
    elif score >= 6:
        return "GOOD"
    elif score >= 2:
        return "MARGINAL"
    else:
        return "NONE"

def process_race(horses: list, weather: dict = None) -> list:
    num_runners = len(horses)
    results = []
    for h in horses:
        if h.get("scratched"):
            continue
        horse = HorseData(
            horse_name=h.get("horse_name", "Unknown"),
            barrier=h.get("barrier", 5),
            jockey=h.get("jockey", ""),
            trainer=h.get("trainer", ""),
            weight=h.get("weight", 56.0),
            tote_odds=h.get("tote_odds", 0.0),
            fixed_odds=h.get("fixed_odds", 0.0),
            days_since_last_run=h.get("days_since_last_run"),
            last_finish=h.get("last_finish"),
            track_condition=h.get("condition"),
            temperature=weather.get("temperature") if weather else None,
            wind_speed=weather.get("wind_speed") if weather else None,
            win_percent=h.get("win_percent", 0.0),
            place_percent=h.get("place_percent", 0.0),
            track_win_percent=h.get("track_win_percent", 0.0),
            distance_win_percent=h.get("distance_win_percent", 0.0),
            condition_win_percent=h.get("condition_win_percent", 0.0),
            career_starts=h.get("career_starts", 0),
            form_string=h.get("form_string", ""),
        )
        results.append(calculate_overlay(horse, num_runners))
    return sorted(results, key=lambda x: x["fair_value"], reverse=True)