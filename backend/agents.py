"""
Enhanced Agent System with AI Strategy Integration
Multi-agent consensus + 10-factor AI analysis
"""
import asyncio
from datetime import datetime, timedelta
from scraper import get_race_fields, get_race_form
from weather import get_all_track_weather
from overlay_model import process_race
from database import SessionLocal, Horse, Race, WeatherData

# Import AI scoring
try:
    from strategy_v3 import score_horse
    AI_AVAILABLE = True
    print("✅ AI Strategy Engine loaded")
except ImportError:
    AI_AVAILABLE = False
    print("⚠️ AI Engine not available - using basic scoring")
    
    def score_horse(h):
        """Fallback basic scoring if AI not available"""
        return {
            "score": h.get("fair_value", 0) * 2,
            "recommendation": "WATCH",
            "bet_type": "NO BET"
        }

# Enhanced state with AI insights
state = {
    "races": [],
    "weather": {},
    "overlays": [],
    "ai_picks": [],  # AI + Agent consensus picks
    "agent_insights": {},
    "last_updated": None,
    "status": "starting",
}

# ═══════════════════════════════════════════════
# SPECIALIZED AGENTS
# ═══════════════════════════════════════════════

class ValueHunterAgent:
    """Agent 1: Focuses on overlay value opportunities"""
    
    def __init__(self):
        self.name = "Value Hunter"
        self.weight = 1.0
    
    def analyze(self, horse_data):
        fair_value = horse_data.get("fair_value", 0)
        track_wins = self._pct(horse_data.get("track_wins", "0"))
        
        score = 0
        reasons = []
        
        if fair_value >= 25:
            score += 40
            reasons.append(f"🎯 Exceptional value ({fair_value:.0f}%)")
        elif fair_value >= 20:
            score += 30
            reasons.append(f"✅ Strong value ({fair_value:.0f}%)")
        elif fair_value >= 15:
            score += 15
            reasons.append(f"📊 Good value ({fair_value:.0f}%)")
        
        if track_wins >= 30:
            score += 20
            reasons.append(f"🏆 Track specialist ({track_wins:.0f}%)")
        
        if AI_AVAILABLE:
            ai = score_horse(horse_data)
            if ai["score"] >= 55:
                score += 15
                reasons.append("🤖 AI confirms")
        
        return {
            "agent": self.name,
            "score": min(score, 100),
            "confidence": "HIGH" if score >= 50 else "MEDIUM" if score >= 30 else "LOW",
            "reasons": reasons,
            "recommendation": "BET" if score >= 45 else "WATCH" if score >= 25 else "SKIP"
        }
    
    def _pct(self, val):
        if isinstance(val, (int, float)):
            return float(val) * 100 if float(val) <= 1.0 else float(val)
        if isinstance(val, str):
            try:
                v = float(val.replace("%", "").strip())
                return v * 100 if v <= 1.0 else v
            except:
                return 0.0
        return 0.0


class FormAnalystAgent:
    """Agent 2: Analyzes recent form and performance trends"""
    
    def __init__(self):
        self.name = "Form Analyst"
        self.weight = 1.0
    
    def analyze(self, horse_data):
        form_string = horse_data.get("form_string", "")
        career_wins = self._pct(horse_data.get("career_wins", "0"))
        
        score = 0
        reasons = []
        
        if form_string:
            positions = [int(c) if c.isdigit() and int(c) > 0 else 10 for c in form_string[:5]]
            if positions:
                wins = sum(1 for p in positions if p == 1)
                places = sum(1 for p in positions if p <= 3)
                avg = sum(positions) / len(positions)
                
                if wins >= 2:
                    score += 35
                    reasons.append(f"🔥 {wins} recent wins")
                elif wins >= 1:
                    score += 20
                    reasons.append(f"✅ Recent winner")
                
                if avg <= 3:
                    score += 25
                    reasons.append(f"📈 Excellent avg ({avg:.1f})")
                elif avg <= 5:
                    score += 12
                    reasons.append(f"📊 Solid avg ({avg:.1f})")
        
        if career_wins >= 25:
            score += 20
            reasons.append(f"💎 Elite record ({career_wins:.0f}%)")
        
        if AI_AVAILABLE:
            ai = score_horse(horse_data)
            if ai["score"] >= 50:
                score += 10
                reasons.append("🤖 AI confirms form")
        
        return {
            "agent": self.name,
            "score": min(score, 100),
            "confidence": "HIGH" if score >= 55 else "MEDIUM" if score >= 35 else "LOW",
            "reasons": reasons,
            "recommendation": "BET" if score >= 50 else "WATCH" if score >= 30 else "SKIP"
        }
    
    def _pct(self, val):
        if isinstance(val, (int, float)):
            return float(val) * 100 if float(val) <= 1.0 else float(val)
        if isinstance(val, str):
            try:
                v = float(val.replace("%", "").strip())
                return v * 100 if v <= 1.0 else v
            except:
                return 0.0
        return 0.0


class TrackSpecialistAgent:
    """Agent 3: Focuses on track/distance/condition suitability"""
    
    def __init__(self):
        self.name = "Track Specialist"
        self.weight = 1.0
    
    def analyze(self, horse_data):
        track_wins = self._pct(horse_data.get("track_wins", "0"))
        dist_wins = self._pct(horse_data.get("dist_wins", "0"))
        
        score = 0
        reasons = []
        
        if track_wins >= 50:
            score += 40
            reasons.append(f"🏆 Track master ({track_wins:.0f}%)")
        elif track_wins >= 30:
            score += 25
            reasons.append(f"✅ Strong at track ({track_wins:.0f}%)")
        elif track_wins >= 15:
            score += 12
            reasons.append(f"📊 Handles track ({track_wins:.0f}%)")
        
        if dist_wins >= 50:
            score += 35
            reasons.append(f"📏 Distance specialist ({dist_wins:.0f}%)")
        elif dist_wins >= 30:
            score += 20
            reasons.append(f"✅ Good at trip ({dist_wins:.0f}%)")
        
        if AI_AVAILABLE:
            ai = score_horse(horse_data)
            if ai["score"] >= 50:
                score += 10
                reasons.append("🤖 AI confirms fit")
        
        return {
            "agent": self.name,
            "score": min(score, 100),
            "confidence": "HIGH" if score >= 60 else "MEDIUM" if score >= 40 else "LOW",
            "reasons": reasons,
            "recommendation": "BET" if score >= 55 else "WATCH" if score >= 35 else "SKIP"
        }
    
    def _pct(self, val):
        if isinstance(val, (int, float)):
            return float(val) * 100 if float(val) <= 1.0 else float(val)
        if isinstance(val, str):
            try:
                v = float(val.replace("%", "").strip())
                return v * 100 if v <= 1.0 else v
            except:
                return 0.0
        return 0.0


# ═══════════════════════════════════════════════
# CONSENSUS BUILDER
# ═══════════════════════════════════════════════

class ConsensusBuilder:
    """Combines all agent opinions into final recommendation"""
    
    def __init__(self):
        self.agents = [
            ValueHunterAgent(),
            FormAnalystAgent(),
            TrackSpecialistAgent()
        ]
    
    def analyze_horse(self, horse_data):
        """Get multi-agent consensus"""
        analyses = [agent.analyze(horse_data) for agent in self.agents]
        
        # Weighted average
        total_score = sum(a["score"] * agent.weight for a, agent in zip(analyses, self.agents))
        total_weight = sum(agent.weight for agent in self.agents)
        consensus_score = total_score / total_weight if total_weight > 0 else 0
        
        # Count votes
        bets = sum(1 for a in analyses if a["recommendation"] == "BET")
        watches = sum(1 for a in analyses if a["recommendation"] == "WATCH")
        
        # Get AI analysis
        ai_analysis = score_horse(horse_data) if AI_AVAILABLE else {"score": 0, "recommendation": "SKIP", "bet_type": "NO BET"}
        
        # Final decision
        if bets >= 2 and ai_analysis["score"] >= 50:
            final_rec = "STRONG BET"
            confidence = "HIGH"
        elif bets >= 2 or (bets >= 1 and ai_analysis["score"] >= 45):
            final_rec = "BET"
            confidence = "MEDIUM"
        elif watches >= 2 or consensus_score >= 30:
            final_rec = "WATCH"
            confidence = "MEDIUM"
        else:
            final_rec = "SKIP"
            confidence = "LOW"
        
        # Collect key reasons
        all_reasons = []
        for a in analyses:
            if a["score"] >= 30:
                all_reasons.extend([f"[{a['agent']}] {r}" for r in a["reasons"][:2]])
        
        return {
            "horse_name": horse_data.get("horse_name", "Unknown"),
            "consensus_score": round(consensus_score, 1),
            "ai_score": round(ai_analysis["score"], 1),
            "final_recommendation": final_rec,
            "confidence": confidence,
            "agent_votes": f"{bets} BET | {watches} WATCH | {3-bets-watches} SKIP",
            "agents_analysis": analyses,
            "key_reasons": all_reasons[:5],
            "ai_recommendation": ai_analysis["recommendation"],
            "bet_type": ai_analysis["bet_type"],
            "track": horse_data.get("track", ""),
            "race_number": horse_data.get("race_number", 0),
            "race_time": horse_data.get("race_time", ""),
            "race_id": horse_data.get("race_id", ""),
            "fair_value": horse_data.get("fair_value", 0),
            "est_odds": horse_data.get("est_fair_odds", 0),
        }


consensus = ConsensusBuilder()


# ═══════════════════════════════════════════════
# ENHANCED OVERLAY CALCULATION
# ═══════════════════════════════════════════════

async def run_overlay_calc():
    """Enhanced overlay calc with AI + 3-agent consensus"""
    try:
        if not state["races"]:
            print("No races loaded yet, skipping overlay calc")
            return
        
        print("🧠 Running AI + Multi-Agent Analysis...")
        all_overlays = []
        all_ai_picks = []
        
        for race in state["races"]:
            weather = state["weather"].get(race["track"], {})
            horses = race.get("horses", [])
            if not horses:
                continue
            
            # Original overlay calculation
            overlays = process_race(horses, weather)
            for o in overlays:
                o["race_id"] = race.get("race_id", "")
                o["track"] = race.get("track", "")
                o["race_number"] = race.get("race_number", 0)
                o["race_time"] = race.get("race_time", "")
                o["race_name"] = race.get("race_name", "")
            all_overlays.extend(overlays)
            
            # AI + Agent consensus analysis
            for horse in horses:
                horse_overlay = next((o for o in overlays if o.get("horse_name") == horse.get("horse_name")), {})
                merged_data = {**horse, **horse_overlay}
                
                consensus_result = consensus.analyze_horse(merged_data)
                
                if consensus_result["final_recommendation"] in ["STRONG BET", "BET"]:
                    all_ai_picks.append(consensus_result)
        
        # Sort
        state["overlays"] = sorted(all_overlays, key=lambda x: x.get("fair_value", 0), reverse=True)
        state["ai_picks"] = sorted(all_ai_picks, key=lambda x: x["consensus_score"], reverse=True)
        
        print(f"✅ Analysis complete:")
        print(f"   📊 {len(state['overlays'])} runners (overlay ranking)")
        print(f"   🤖 {len(state['ai_picks'])} AI picks (multi-agent consensus)")
        if state['ai_picks']:
            top = state['ai_picks'][0]
            print(f"   🎯 Top: {top['horse_name']} ({top['consensus_score']:.0f}/100, {top['final_recommendation']})")
        
    except Exception as e:
        print(f"❌ Overlay calc error: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════════════════════════════
# BACKGROUND AGENTS
# ═══════════════════════════════════════════════

async def race_scraper_agent():
    """Agent: Scrape race data"""
    while True:
        try:
            print("Running race scraper...")
            races = await get_race_fields()
            state["races"] = races
            state["last_updated"] = datetime.utcnow().isoformat()
            state["status"] = "running"
            save_races_to_db(races)
            print(f"✅ Loaded {len(races)} races")
        except Exception as e:
            print(f"❌ Race scraper error: {e}")
            state["status"] = "error"
        await asyncio.sleep(300)  # 5 min


async def weather_agent():
    """Agent: Fetch weather data"""
    while True:
        try:
            print("Fetching weather...")
            weather_list = await get_all_track_weather()
            for w in weather_list:
                state["weather"][w["track"]] = w
            save_weather_to_db(weather_list)
            print(f"✅ Weather: {len(weather_list)} tracks")
        except Exception as e:
            print(f"❌ Weather error: {e}")
        await asyncio.sleep(600)  # 10 min


async def overlay_agent():
    """Agent: Calculate overlays + AI analysis"""
    # Wait for data
    waited = 0
    while not state["races"] and waited < 120:
        await asyncio.sleep(5)
        waited += 5
    
    while True:
        await run_overlay_calc()
        await asyncio.sleep(180)  # 3 min


async def odds_monitor_agent():
    """Agent: Monitor odds movements"""
    previous_odds = {}
    while True:
        try:
            print("Monitoring odds...")
            for race in state["races"]:
                for horse in race.get("horses", []):
                    key = f"{race.get('race_id')}_{horse.get('horse_name')}"
                    current = horse.get("tote_odds", 0)
                    if key in previous_odds and previous_odds[key] > 0 and current > 0:
                        movement = ((current - previous_odds[key]) / previous_odds[key]) * 100
                        if abs(movement) >= 15:
                            print(f"💨 ODDS MOVE: {horse.get('horse_name')} "
                                  f"{previous_odds[key]:.2f} → {current:.2f} ({movement:+.0f}%)")
                    previous_odds[key] = current
        except Exception as e:
            print(f"❌ Odds monitor error: {e}")
        await asyncio.sleep(60)


async def scratch_detection_agent():
    """Agent: Detect and remove scratchings"""
    await asyncio.sleep(1800)  # Wait 30 min
    
    while True:
        try:
            if not state["races"]:
                await asyncio.sleep(1800)
                continue
            
            print("🔍 Checking scratchings...")
            today = datetime.now().strftime("%Y-%m-%d")
            total_removed = 0
            
            for race in state["races"]:
                slug = race.get("race_id", "").split("_")[0]
                race_number = race.get("race_number")
                if not slug or not race_number:
                    continue
                
                form_data = await get_race_form(today, slug, race_number)
                if not form_data or not isinstance(form_data, dict):
                    continue
                
                runners = form_data.get("runners") or []
                scratched = {r.get("name", "").strip() for r in runners if r and r.get("scratched")}
                
                if scratched:
                    before = len(race["horses"])
                    race["horses"] = [h for h in race["horses"] if h.get("horse_name", "").strip() not in scratched]
                    removed = before - len(race["horses"])
                    if removed > 0:
                        total_removed += removed
                        print(f"❌ {race['track']} R{race['race_number']}: removed {removed} — {scratched}")
                
                await asyncio.sleep(0.3)
            
            if total_removed > 0:
                print(f"🔄 {total_removed} scratchings, recalculating...")
                await run_overlay_calc()
                state["last_updated"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            print(f"❌ Scratch detection error: {e}")
        
        await asyncio.sleep(1800)  # 30 min


async def cleanup_agent():
    """Agent: Clean old database records"""
    while True:
        try:
            db = SessionLocal()
            cutoff = datetime.utcnow() - timedelta(hours=24)
            deleted = db.query(WeatherData).filter(WeatherData.recorded_at < cutoff).delete()
            db.commit()
            db.close()
            print(f"🧹 Cleanup: removed {deleted} old weather records")
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
        await asyncio.sleep(3600)  # 1 hour


# ═══════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════

def save_races_to_db(races):
    """Save races and horses to database"""
    db = SessionLocal()
    try:
        for race in races:
            existing = db.query(Race).filter(Race.race_id == race["race_id"]).first()
            if not existing:
                db.add(Race(
                    race_id=race["race_id"],
                    track=race["track"],
                    race_number=race["race_number"],
                    race_time=race["race_time"],
                    distance=race["distance"],
                    condition=race["condition"],
                ))
            
            for horse in race.get("horses", []):
                existing_horse = db.query(Horse).filter(
                    Horse.race_id == race["race_id"],
                    Horse.horse_name == horse["horse_name"]
                ).first()
                
                if existing_horse:
                    existing_horse.tote_odds = horse.get("tote_odds", 0)
                    existing_horse.fixed_odds = horse.get("fixed_odds", 0)
                    existing_horse.updated_at = datetime.utcnow()
                else:
                    db.add(Horse(
                        race_id=race["race_id"],
                        horse_name=horse.get("horse_name", ""),
                        barrier=horse.get("barrier", 0),
                        jockey=horse.get("jockey", ""),
                        trainer=horse.get("trainer", ""),
                        weight=horse.get("weight", 0),
                        tote_odds=horse.get("tote_odds", 0),
                        fixed_odds=horse.get("fixed_odds", 0),
                    ))
        db.commit()
    except Exception as e:
        print(f"❌ DB save error: {e}")
        db.rollback()
    finally:
        db.close()


def save_weather_to_db(weather_list):
    """Save weather data to database"""
    db = SessionLocal()
    try:
        for w in weather_list:
            db.add(WeatherData(
                track=w["track"],
                temperature=w["temperature"],
                humidity=w["humidity"],
                wind_speed=w["wind_speed"],
                conditions=w["conditions"],
            ))
        db.commit()
    except Exception as e:
        print(f"❌ Weather DB error: {e}")
        db.rollback()
    finally:
        db.close()


# ═══════════════════════════════════════════════
# START ALL AGENTS
# ═══════════════════════════════════════════════

async def start_all_agents():
    """Launch all background agents"""
    print("=" * 60)
    print("🚀 ENHANCED AGENT SYSTEM v2.0")
    print("=" * 60)
    print("📋 Agents:")
    print("   🔍 Race Scraper (every 5 min)")
    print("   🌧️  Weather Monitor (every 10 min)")
    print("   🧮 Overlay Calculator + AI (every 3 min)")
    print("   💨 Odds Monitor (every 1 min)")
    print("   ❌ Scratch Detection (every 30 min)")
    print("   🧹 Database Cleanup (every 1 hour)")
    print("")
    print("🤖 AI Agents:")
    print("   🎯 Value Hunter")
    print("   🔥 Form Analyst")
    print("   🏆 Track Specialist")
    print("   + 10-Factor AI Engine" if AI_AVAILABLE else "   (AI Engine not loaded)")
    print("=" * 60)
    print("Starting in 20 seconds...")
    await asyncio.sleep(20)
    
    await asyncio.gather(
        race_scraper_agent(),
        weather_agent(),
        overlay_agent(),
        odds_monitor_agent(),
        scratch_detection_agent(),
        cleanup_agent(),
    )


# Export for main.py
__all__ = ["state", "start_all_agents", "consensus"]
