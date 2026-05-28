"""
AI Betting Strategy Engine v3 - Clean Working Version
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
import httpx
import uvicorn

app = FastAPI(title="AI Strategy Engine v3", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OVERLAY_API = "https://punting-lab-backend.onrender.com"


def pct(val) -> float:
    """Parse percentage to float."""
    if isinstance(val, (int, float)):
        return float(val) * 100 if float(val) <= 1.0 else float(val)
    if isinstance(val, str):
        try:
            v = float(val.replace("%", "").strip())
            return v * 100 if v <= 1.0 else v
        except:
            return 0.0
    return 0.0


def parse_form(form_str: str) -> List[int]:
    """Parse form string like '106X2' to positions."""
    result = []
    for c in form_str:
        if c == "X":
            result.append(99)
        elif c.isdigit():
            result.append(int(c) if int(c) > 0 else 10)
    return result


def score_horse(h: dict) -> dict:
    """Score a horse across 10 factors. Returns dict with all info."""
    
    name = h.get("horse_name", "Unknown")
    fair_value = h.get("fair_value", 0)
    est_odds = h.get("est_fair_odds", 0)
    track_wins = pct(h.get("track_wins", "0%"))
    dist_wins = pct(h.get("dist_wins", "0%"))
    career_wins = pct(h.get("career_wins", "0%"))
    cond_wins = pct(h.get("condition_win_percent", 0)) or pct(h.get("condition_wins", "0%"))
    form_str = h.get("form_string", "")
    barrier = h.get("barrier", 0)
    weight = h.get("weight", 0)
    jockey = h.get("jockey", "")
    trainer = h.get("trainer", "")
    race_name = h.get("race_name", "")
    career_starts = h.get("career_starts", 0)
    
    # ── Factor 1: Overlay Value (18%) ──
    if fair_value >= 25:
        f1 = (1.0, "EXCELLENT", f"Outstanding value - {fair_value:.1f}% fair value (est odds {est_odds:.2f})")
    elif fair_value >= 20:
        f1 = (0.8, "GOOD", f"Strong value - {fair_value:.1f}% fair value (est odds {est_odds:.2f})")
    elif fair_value >= 15:
        f1 = (0.6, "AVERAGE", f"Moderate value - {fair_value:.1f}% fair value")
    elif fair_value >= 10:
        f1 = (0.3, "POOR", f"Limited value - {fair_value:.1f}% fair value")
    else:
        f1 = (0.1, "AVOID", f"No value - {fair_value:.1f}% fair value")
    
    # ── Factor 2: Track Form (12%) ──
    if track_wins >= 40:
        f2 = (1.0, "EXCELLENT", f"Track specialist - {track_wins:.0f}% win rate at this track")
    elif track_wins >= 25:
        f2 = (0.7, "GOOD", f"Good at track - {track_wins:.0f}% win rate")
    elif track_wins >= 10:
        f2 = (0.4, "AVERAGE", f"Average at track - {track_wins:.0f}% win rate")
    elif track_wins > 0:
        f2 = (0.2, "POOR", f"Below par at track - {track_wins:.0f}% win rate")
    else:
        f2 = (0.0, "UNKNOWN", f"No track record - first time at track")
    
    # ── Factor 3: Distance Form (10%) ──
    if dist_wins >= 40:
        f3 = (1.0, "EXCELLENT", f"Distance specialist - {dist_wins:.0f}% win rate at this trip")
    elif dist_wins >= 25:
        f3 = (0.7, "GOOD", f"Good at distance - {dist_wins:.0f}% win rate")
    elif dist_wins >= 10:
        f3 = (0.4, "AVERAGE", f"Average at distance - {dist_wins:.0f}% win rate")
    elif dist_wins > 0:
        f3 = (0.2, "POOR", f"Below par at distance - {dist_wins:.0f}% win rate")
    else:
        f3 = (0.0, "UNKNOWN", f"No distance record")
    
    # ── Factor 4: Recent Form (14%) ──
    positions = parse_form(form_str)
    if not positions:
        f4 = (0.2, "POOR", "No recent form available")
    else:
        recent = positions[:5]
        avg = sum(recent) / len(recent)
        wins = sum(1 for p in recent if p == 1)
        places = sum(1 for p in recent if p <= 3)
        
        base = 0
        if wins >= 2: base += 0.4
        elif wins >= 1: base += 0.25
        if places / len(recent) >= 0.8: base += 0.3
        elif places / len(recent) >= 0.5: base += 0.2
        if avg <= 2.5: base += 0.2
        elif avg <= 4.0: base += 0.1
        
        base = min(max(base, 0.0), 1.0)
        
        if base >= 0.7:
            f4 = (base, "EXCELLENT", f"Brilliant form - {wins}W {places}P from {len(recent)} runs, avg {avg:.1f}")
        elif base >= 0.5:
            f4 = (base, "GOOD", f"Solid form - {wins}W {places}P from {len(recent)} runs, avg {avg:.1f}")
        elif base >= 0.3:
            f4 = (base, "AVERAGE", f"Fair form - {wins}W {places}P from {len(recent)} runs, avg {avg:.1f}")
        else:
            f4 = (base, "POOR", f"Poor form - {wins}W {places}P from {len(recent)} runs, avg {avg:.1f}")
    
    # ── Factor 5: Condition Form (10%) ──
    if cond_wins >= 40:
        f5 = (1.0, "EXCELLENT", f"Condition specialist - {cond_wins:.0f}% win rate")
    elif cond_wins >= 25:
        f5 = (0.7, "GOOD", f"Good in condition - {cond_wins:.0f}% win rate")
    elif cond_wins >= 10:
        f5 = (0.4, "AVERAGE", f"Average in condition - {cond_wins:.0f}% win rate")
    elif cond_wins > 0:
        f5 = (0.2, "POOR", f"Struggles in condition - {cond_wins:.0f}% win rate")
    else:
        f5 = (0.3, "UNKNOWN", f"No condition data available")
    
    # ── Factor 6: Career Consistency (8%) ──
    if career_starts < 3:
        f6 = (0.3, "UNKNOWN", f"Only {career_starts} career starts")
    elif career_wins >= 25:
        f6 = (1.0, "EXCELLENT", f"Elite - {career_wins:.0f}% win rate from {career_starts} starts")
    elif career_wins >= 20:
        f6 = (0.7, "GOOD", f"Reliable - {career_wins:.0f}% win rate from {career_starts} starts")
    elif career_wins >= 10:
        f6 = (0.4, "AVERAGE", f"Average - {career_wins:.0f}% win rate from {career_starts} starts")
    elif career_wins > 0:
        f6 = (0.2, "POOR", f"Low win rate - {career_wins:.0f}% from {career_starts} starts")
    else:
        f6 = (0.0, "AVOID", f"No wins from {career_starts} starts")
    
    # ── Factor 7: Jockey/Trainer (8%) ──
    top_jockeys = ["Jye McNeil", "Beau Mertens", "Damien Thornton", "Patrick Moloney", "Craig Newitt", "Teo Nugent", "Zac Spain", "Ben Allen"]
    top_trainers = ["Ciaron Maher", "Anthony & Sam Freedman", "Peter G Moody", "Patrick Payne", "Enver Jusufovic", "Jason Warren", "Trent Busuttin", "Matt Laurie"]
    
    j_score = 0.7 if jockey in top_jockeys else 0.3
    t_score = 0.7 if any(t in trainer for t in top_trainers) else 0.3
    combined = (j_score + t_score) / 2
    
    if combined >= 0.6:
        f7 = (0.8, "GOOD", f"Strong combo - {jockey} for {trainer}")
    else:
        f7 = (0.3, "AVERAGE", f"Average combo - {jockey} for {trainer}")
    
    # ── Factor 8: Weight (6%) ──
    if not weight or weight == 0:
        f8 = (0.5, "UNKNOWN", "No weight data")
    elif weight >= 60:
        f8 = (0.3, "POOR", f"Top weight ({weight}kg) - burden")
    elif weight >= 58:
        f8 = (0.5, "AVERAGE", f"Average weight ({weight}kg)")
    elif weight >= 56:
        f8 = (0.7, "GOOD", f"Favourable weight ({weight}kg)")
    else:
        f8 = (0.9, "EXCELLENT", f"Light weight ({weight}kg) - advantage")
    
    # ── Factor 9: Barrier (6%) ──
    if not barrier or barrier == 0:
        f9 = (0.5, "UNKNOWN", "No barrier data")
    elif barrier <= 4:
        f9 = (0.8, "GOOD", f"Low barrier ({barrier}) - good draw")
    elif barrier <= 8:
        f9 = (0.5, "AVERAGE", f"Middle barrier ({barrier})")
    elif barrier <= 12:
        f9 = (0.3, "POOR", f"Wide barrier ({barrier})")
    else:
        f9 = (0.15, "AVOID", f"Very wide ({barrier})")
    
    # ── Factor 10: Class Fit (8%) ──
    is_maiden = "Maiden" in race_name
    if is_maiden and career_wins > 0:
        f10 = (0.8, "GOOD", f"Dropping to maiden with {career_wins:.0f}% win rate")
    elif career_wins >= 25:
        f10 = (0.7, "GOOD", f"Proven class - {career_wins:.0f}% win rate")
    elif career_wins >= 15:
        f10 = (0.4, "AVERAGE", f"Adequate class - {career_wins:.0f}% win rate")
    else:
        f10 = (0.3, "POOR", f"May struggle at this class - {career_wins:.0f}% win rate")
    
    # ── Calculate Total Score ──
    factors = [
        ("Overlay Value", f1, 0.18),
        ("Track Form", f2, 0.12),
        ("Distance Form", f3, 0.10),
        ("Recent Form", f4, 0.14),
        ("Condition Form", f5, 0.10),
        ("Career Consistency", f6, 0.08),
        ("Jockey/Trainer", f7, 0.08),
        ("Weight", f8, 0.06),
        ("Barrier", f9, 0.06),
        ("Class Fit", f10, 0.08),
    ]
    
    total = sum(f[1][0] * f[2] for f in factors) * 100  # 0-100
    
    # Recommendation
    if total >= 55:
        rec = "STRONG BET"
    elif total >= 42:
        rec = "BET"
    elif total >= 30:
        rec = "WATCH"
    else:
        rec = "AVOID"
    
    # Bet type
    if total >= 50:
        bet_type = "WIN"
    elif total >= 38:
        bet_type = "EACH WAY"
    elif total >= 30:
        bet_type = "PLACE"
    else:
        bet_type = "NO BET"
    
    # Strengths & weaknesses
    strengths = [f"{fname}: {f[1][1]}" for fname, f, w in factors if f[1][1] in ["EXCELLENT", "GOOD"]]
    weaknesses = [f"{fname}: {f[1][1]}" for fname, f, w in factors if f[1][1] in ["POOR", "AVOID"]]
    
    # Best factor
    best = max(factors, key=lambda x: x[1][0] * x[2])
    key_reason = f"{best[0]}: {best[1][2]}"
    
    # Edge
    edge = max(fair_value - 10, 0)
    
    # Confidence
    excellent = sum(1 for _, f, _ in factors if f[1] == "EXCELLENT")
    poor = sum(1 for _, f, _ in factors if f[1] in ["POOR", "AVOID"])
    if excellent >= 3 and poor <= 2:
        confidence = "HIGH"
    elif excellent >= 1 and poor <= 3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    # Risk
    if poor >= 4:
        risk = "HIGH"
    elif poor >= 2:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    
    return {
        "horse": name,
        "track": h.get("track", ""),
        "race_number": h.get("race_number", 0),
        "race_time": h.get("race_time", ""),
        "race_name": race_name,
        "score": round(total, 1),
        "recommendation": rec,
        "bet_type": bet_type,
        "confidence": confidence,
        "risk": risk,
        "edge": round(edge, 1),
        "fair_value": round(fair_value, 1),
        "est_odds": round(est_odds, 2),
        "key_reason": key_reason,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "factors": [
            {"name": fname, "score": round(f[0], 2), "rating": f[1], "detail": f[2], "weight": w}
            for fname, f, w in factors
        ]
    }


@app.get("/")
async def root():
    return {"message": "🎯 AI Strategy Engine v3", "status": "online", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/recommendations")
async def get_recommendations():
    """Get betting recommendations for all races."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OVERLAY_API}/api/overlays", timeout=15.0)
            data = response.json()
        
        overlays = data.get("overlays", [])
        
        # Score every horse
        scored = [score_horse(h) for h in overlays]
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        # Group by race
        races = {}
        for h in overlays:
            rid = h.get("race_id", "unknown")
            if rid not in races:
                races[rid] = {"info": h, "horses": []}
            races[rid]["horses"].append(h)
        
        # Race summaries
        race_summaries = []
        for rid, race_data in races.items():
            info = race_data["info"]
            race_scored = [score_horse(h) for h in race_data["horses"]]
            race_scored.sort(key=lambda x: x["score"], reverse=True)
            best = race_scored[0] if race_scored else None
            
            race_summaries.append({
                "race_id": rid,
                "race": f"{info.get('track', '')} R{info.get('race_number', '')} ({info.get('race_time', '')})",
                "name": info.get("race_name", ""),
                "field_size": len(race_data["horses"]),
                "best_horse": best["horse"] if best else None,
                "best_score": best["score"] if best else 0,
                "best_rec": best["recommendation"] if best else "N/A",
                "summary": f"Best: {best['horse']} ({best['score']}/100 - {best['recommendation']})" if best else "No data"
            })
        
        # Count recommendations
        strong = sum(1 for s in scored if s["recommendation"] == "STRONG BET")
        bets = sum(1 for s in scored if s["recommendation"] in ["STRONG BET", "BET"])
        watches = sum(1 for s in scored if s["recommendation"] == "WATCH")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_runners": len(overlays),
            "strong_bets": strong,
            "bets": bets,
            "watches": watches,
            "top_10": scored[:10],
            "race_summaries": race_summaries
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>🎯 AI Strategy v3</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .btn {{ padding: 12px 24px; background: #2196f3; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 5px; font-size: 16px; }}
        .btn:hover {{ background: #1976d2; }}
        .bet {{ padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 5px solid #2196f3; background: #f9f9f9; }}
        .bet.strong {{ border-left-color: #4caf50; background: #e8f5e8; }}
        .bet.bet {{ border-left-color: #2196f3; background: #e3f2fd; }}
        .bet.watch {{ border-left-color: #ff9800; background: #fff3e0; }}
        .bet.avoid {{ border-left-color: #9e9e9e; background: #f5f5f5; }}
        .score-bar {{ height: 20px; background: #e0e0e0; border-radius: 10px; margin: 5px 0; overflow: hidden; }}
        .score-fill {{ height: 100%; border-radius: 10px; }}
        .race {{ padding: 12px; margin: 8px 0; background: #f0f0f0; border-radius: 8px; }}
        .factor-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin: 8px 0; }}
        .factor {{ padding: 6px; border-radius: 4px; font-size: 11px; text-align: center; }}
        .factor.excellent {{ background: #c8e6c9; }}
        .factor.good {{ background: #bbdefb; }}
        .factor.average {{ background: #f5f5f5; }}
        .factor.poor {{ background: #ffe0b2; }}
        .factor.unknown {{ background: #e0e0e0; }}
        .factor.avoid {{ background: #ffcdd2; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 15px 0; }}
        .stat {{ text-align: center; padding: 15px; background: #f5f5f5; border-radius: 8px; }}
        .stat .num {{ font-size: 28px; font-weight: bold; color: #2196f3; }}
        .stat .label {{ font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 AI Betting Strategy <small style="font-size: 14px; color: #666;">v3 — 10-Factor Analysis</small></h1>
        
        <div class="card">
            <p><strong>Status:</strong> ✅ Online | <strong>Factors:</strong> 10 | <strong>Time:</strong> {now}</p>
        </div>
        
        <div class="card">
            <button class="btn" onclick="load()">🔄 Analyze All Runners</button>
            <div id="stats" class="stats" style="display:none;"></div>
            <div id="results"></div>
        </div>
        
        <div class="card">
            <h2>🏁 Race Summaries</h2>
            <div id="races"><p>Click "Analyze All Runners" to see race-by-race breakdown</p></div>
        </div>
        
        <div class="card">
            <h2>🧠 The 10 Factors</h2>
            <div class="factor-grid">
                <div class="factor good">🎯 Overlay Value<br><small>18%</small></div>
                <div class="factor good">🏆 Track Form<br><small>12%</small></div>
                <div class="factor good">📏 Distance Form<br><small>10%</small></div>
                <div class="factor good">🔥 Recent Form<br><small>14%</small></div>
                <div class="factor good">🌧️ Condition<br><small>10%</small></div>
                <div class="factor good">💎 Consistency<br><small>8%</small></div>
                <div class="factor good">🏇 Jockey/Trainer<br><small>8%</small></div>
                <div class="factor good">⚖️ Weight<br><small>6%</small></div>
                <div class="factor good">🏁 Barrier<br><small>6%</small></div>
                <div class="factor good">📊 Class Fit<br><small>8%</small></div>
            </div>
        </div>
    </div>

    <script>
        async function load() {{
            const results = document.getElementById('results');
            const racesDiv = document.getElementById('races');
            const statsDiv = document.getElementById('stats');
            results.innerHTML = '<p>🔄 Analyzing...</p>';
            
            try {{
                const res = await fetch('/api/recommendations');
                const data = await res.json();
                
                // Stats
                statsDiv.style.display = 'grid';
                statsDiv.innerHTML = `
                    <div class="stat"><div class="num">${{data.total_runners}}</div><div class="label">Runners</div></div>
                    <div class="stat"><div class="num" style="color:#4caf50">${{data.strong_bets}}</div><div class="label">Strong Bets</div></div>
                    <div class="stat"><div class="num" style="color:#2196f3">${{data.bets}}</div><div class="label">Bets</div></div>
                    <div class="stat"><div class="num" style="color:#ff9800">${{data.watches}}</div><div class="label">Watches</div></div>
                `;
                
                // Top 10
                const bets = data.top_10 || [];
                let html = '<h2>🏆 Top 10 AI Picks</h2>';
                
                if (bets.length === 0) {{
                    html += '<p>No runners found.</p>';
                }} else {{
                    bets.forEach((b, i) => {{
                        const cls = b.recommendation === 'STRONG BET' ? 'strong' : 
                                    b.recommendation === 'BET' ? 'bet' : 
                                    b.recommendation === 'WATCH' ? 'watch' : 'avoid';
                        const color = cls === 'strong' ? '#4caf50' : cls === 'bet' ? '#2196f3' : cls === 'watch' ? '#ff9800' : '#9e9e9e';
                        const pct = Math.min(b.score, 100);
                        
                        html += `
                            <div class="bet ${{cls}}">
                                <h3>#${{i+1}}: ${{b.horse}} <small style="color:#666;">${{b.track}} R${{b.race_number}} (${{b.race_time}})</small></h3>
                                <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin:8px 0;">
                                    <div><strong>Score:</strong> ${{b.score}}/100</div>
                                    <div><strong>Rec:</strong> <span style="color:${{color}};font-weight:bold;">${{b.recommendation}}</span></div>
                                    <div><strong>Bet:</strong> ${{b.bet_type}}</div>
                                    <div><strong>Edge:</strong> ${{b.edge}}%</div>
                                    <div><strong>Fair:</strong> ${{b.fair_value}}%</div>
                                </div>
                                <div class="score-bar"><div class="score-fill" style="width:${{pct}}%; background:${{color}};"></div></div>
                                <p style="margin:8px 0 4px;"><strong>🔑 Key:</strong> ${{b.key_reason}}</p>
                                ${{b.strengths.length > 0 ? '<p style="margin:4px 0;color:#4caf50;"><strong>✅ Strengths:</strong> ' + b.strengths.join(' | ') + '</p>' : ''}}
                                ${{b.weaknesses.length > 0 ? '<p style="margin:4px 0;color:#f44336;"><strong>⚠️ Weaknesses:</strong> ' + b.weaknesses.join(' | ') + '</p>' : ''}}
                                <div class="factor-grid">
                                    ${{b.factors.map(f => '<div class="factor ' + f.rating.toLowerCase().replace(' ','') + '">' + f.name + '<br><strong>' + f.rating + '</strong></div>').join('')}}
                                </div>
                            </div>
                        `;
                    }});
                }}
                results.innerHTML = html;
                
                // Races
                const races = data.race_summaries || [];
                let rhtml = '';
                races.forEach(r => {{
                    const color = r.best_score >= 55 ? '#4caf50' : r.best_score >= 42 ? '#2196f3' : r.best_score >= 30 ? '#ff9800' : '#9e9e9e';
                    rhtml += `
                        <div class="race">
                            <strong>${{r.race}}</strong> — ${{r.name}}<br>
                            <small>${{r.field_size}} runners | Best: <strong style="color:${{color}}">${{r.best_horse}}</strong> (${{r.best_score}}/100 - ${{r.best_rec}})</small>
                        </div>
                    `;
                }});
                racesDiv.innerHTML = rhtml || '<p>No races found</p>';
                
            }} catch (err) {{
                results.innerHTML = '<p style="color:red;">Error: ' + err.message + '</p>';
                console.error(err);
            }}
        }}
    </script>
</body>
</html>
    """)


if __name__ == "__main__":
    print("🚀 AI Strategy Engine v3")
    print(f"📊 Overlay API: {OVERLAY_API}")
    print("🌐 Dashboard: http://localhost:8003/dashboard")
    uvicorn.run("strategy_v3:app", host="0.0.0.0", port=8003, reload=False)
