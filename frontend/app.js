const API = "https://punting-lab-backend.onrender.com";
let allOverlays = [];
let allRaces = [];
let ws = null;
let countdownInterval = null;
let raceResults = {};

document.addEventListener("DOMContentLoaded", function() {
    loadResultsFromDB();
    fetchData();
    connectWebSocket();
    setInterval(fetchData, 60000);
    startCountdownTick();
    document.getElementById("filter-rating").addEventListener("change", renderRaceCards);
    document.getElementById("filter-track").addEventListener("change", renderRaceCards);
    document.getElementById("filter-sort").addEventListener("change", renderRaceCards);
});

function connectWebSocket() {
    try {
        ws = new WebSocket("wss://punting-lab-backend.onrender.com/ws");
        ws.onopen = function() { setStatus("green", "Live"); };
        ws.onmessage = function(event) {
            var data = JSON.parse(event.data);
            if (data.overlays) {
                allOverlays = data.overlays;
                renderRaceCards();
                updateSummaryCards();
                populateTrackFilter();
            }
            if (data.weather) renderWeather(data.weather);
            if (data.last_updated) setUpdated(data.last_updated);
        };
        ws.onerror = function() { setStatus("red", "Connection error"); };
        ws.onclose = function() {
            setStatus("grey", "Reconnecting...");
            setTimeout(connectWebSocket, 5000);
        };
    } catch(e) {
        setStatus("red", "WS Error");
        setTimeout(connectWebSocket, 5000);
    }
}

function fetchData() {
    fetch(API + "/api/overlays")
        .then(function(r) { return r.json(); })
        .then(function(overlayData) {
            allOverlays = overlayData.overlays || [];
            renderRaceCards();
            updateSummaryCards();
            populateTrackFilter();
            if (overlayData.last_updated) setUpdated(overlayData.last_updated);
            setStatus("green", "Live");
        })
        .catch(function() { setStatus("red", "Offline"); });

    fetch(API + "/api/weather")
        .then(function(r) { return r.json(); })
        .then(function(d) { renderWeather(d.weather || {}); })
        .catch(function() {});

    fetch(API + "/api/status")
        .then(function(r) { return r.json(); })
        .then(function(d) {
            document.getElementById("races-count").textContent = d.races_loaded || 0;
        })
        .catch(function() {});

    loadAccuracy();

    fetch(API + "/api/races")
        .then(function(r) { return r.json(); })
        .then(function(d) { allRaces = d.races || []; updateNextRaceBanner(); })
        .catch(function() {});
}

function loadResultsFromDB() {
    fetch(API + "/api/results")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var results = data.results || [];
            for (var i = 0; i < results.length; i++) {
                var r = results[i];
                var key = r.track + "_" + r.race_number;
                raceResults[key] = { winner: r.winner, second: r.second, third: r.third };
            }
            renderRaceCards();
        })
        .catch(function() {});
}

function loadAccuracy() {
    fetch(API + "/api/accuracy")
        .then(function(r) { return r.json(); })
        .then(function(d) {
            var section = document.getElementById("accuracy-section");
            if (d.total_races > 0) {
                section.style.display = "block";
                document.getElementById("acc-total").textContent = d.total_races;
                document.getElementById("acc-wins").textContent = d.wins;
                document.getElementById("acc-winrate").textContent = d.win_rate + "%";
                document.getElementById("acc-placerate").textContent = d.place_rate + "%";
            }
        })
        .catch(function() {});

    fetch(API + "/api/results")
        .then(function(r) { return r.json(); })
        .then(function(d) {
            var results = d.results || [];
            var tbody = document.getElementById("accuracy-tbody");
            if (!results.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="loading">No results recorded yet.</td></tr>';
                return;
            }
            var section = document.getElementById("accuracy-section");
            section.style.display = "block";
            var html = "";
            for (var i = 0; i < results.length; i++) {
                var r = results[i];
                var resultClass = r.model_top_pick_won ? "result-win" :
                                  r.model_top_pick_placed ? "result-place" : "result-loss";
                var resultText = r.model_top_pick_won ? "✅ WIN" :
                                 r.model_top_pick_placed ? "📍 PLACE" :
                                 r.model_top_pick ? "❌ LOSS" : "—";
                html += '<tr>' +
                    '<td>' + (r.race_date || "--") + '</td>' +
                    '<td>' + (r.track || "--") + '</td>' +
                    '<td>R' + (r.race_number || "--") + '</td>' +
                    '<td><strong>' + (r.model_top_pick || "--") + '</strong></td>' +
                    '<td class="result-win">' + (r.winner || "--") + '</td>' +
                    '<td style="color:#c0c0c0">' + (r.second || "--") + '</td>' +
                    '<td style="color:#cd7f32">' + (r.third || "--") + '</td>' +
                    '<td class="' + resultClass + '">' + resultText + '</td>' +
                    '</tr>';
            }
            tbody.innerHTML = html;
        })
        .catch(function() {});
}

function startCountdownTick() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(function() {
        updateNextRaceBanner();
        updateRaceTimers();
        updateBetCardTimers();
    }, 1000);
}

function parseRaceTime(timeStr) {
    if (!timeStr || timeStr === "00:00") return null;
    var now = new Date();
    var parts = timeStr.split(":");
    var h = parseInt(parts[0]);
    var m = parseInt(parts[1]);
    return new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);
}

function secondsUntil(timeStr) {
    var d = parseRaceTime(timeStr);
    if (!d) return null;
    return Math.floor((d - new Date()) / 1000);
}

function isResulted(timeStr) {
    var secs = secondsUntil(timeStr);
    return secs !== null && secs < -2700;
}

function formatCountdown(seconds) {
    if (seconds <= 0) return "LIVE";
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h > 0) return h + ":" + pad(m) + ":" + pad(s);
    return pad(m) + ":" + pad(s);
}

function pad(n) { return n < 10 ? "0" + n : "" + n; }

function timerClass(seconds) {
    if (seconds <= 0)   return "live";
    if (seconds <= 120) return "urgent";
    if (seconds <= 600) return "soon";
    return "";
}

function updateNextRaceBanner() {
    if (!allRaces.length) return;
    var nearest = null;
    var nearestSecs = Infinity;
    for (var i = 0; i < allRaces.length; i++) {
        var secs = secondsUntil(allRaces[i].race_time);
        if (secs !== null && secs > -60 && secs < nearestSecs) {
            nearestSecs = secs;
            nearest = allRaces[i];
        }
    }
    var banner = document.getElementById("next-race-banner");
    if (!nearest) { banner.style.display = "none"; return; }
    banner.style.display = "block";
    document.getElementById("next-race-name").textContent =
        nearest.track + " R" + nearest.race_number + " — " + (nearest.race_name || nearest.distance || "");
    var el = document.getElementById("next-race-countdown");
    el.textContent = formatCountdown(nearestSecs);
    el.className = "next-race-countdown " + timerClass(nearestSecs);
}

function updateRaceTimers() {
    var timers = document.querySelectorAll(".race-timer[data-time]");
    for (var i = 0; i < timers.length; i++) {
        var el = timers[i];
        var timeStr = el.getAttribute("data-time");
        if (isResulted(timeStr)) {
            el.textContent = "Resulted";
            el.className = "race-timer resulted";
        } else {
            var secs = secondsUntil(timeStr);
            if (secs === null) continue;
            el.textContent = formatCountdown(secs);
            el.className = "race-timer " + timerClass(secs);
        }
    }
}

function updateBetCardTimers() {
    var timers = document.querySelectorAll(".bet-timer[data-time]");
    for (var i = 0; i < timers.length; i++) {
        var el = timers[i];
        var secs = secondsUntil(el.getAttribute("data-time"));
        if (secs === null) continue;
        el.textContent = formatCountdown(secs);
        el.className = "bet-timer " + timerClass(secs);
    }
}

function resultKey(track, raceNumber) { return track + "_" + raceNumber; }

function getResult(track, raceNumber) {
    return raceResults[resultKey(track, raceNumber)] || null;
}

function showResultInput(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var footer = document.getElementById("result-footer-" + key);
    if (!footer) return;
    footer.innerHTML =
        '<div class="result-input-row">' +
        '<input class="result-input" id="winner-' + key + '" placeholder="1st place..." />' +
        '<input class="result-input" id="second-' + key + '" placeholder="2nd..." style="max-width:120px"/>' +
        '<input class="result-input" id="third-'  + key + '" placeholder="3rd..." style="max-width:120px"/>' +
        '<button class="result-save-btn" onclick="submitResult(\'' + track + '\',' + raceNumber + ')">Save</button>' +
        '<button class="result-cancel-btn" onclick="renderResultFooter(\'' + track + '\',' + raceNumber + ')">✕</button>' +
        '</div>';
    var inp = document.getElementById("winner-" + key);
    if (inp) inp.focus();
}

function submitResult(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var winner = (document.getElementById("winner-" + key) || {}).value || "";
    var second = (document.getElementById("second-" + key) || {}).value || "";
    var third  = (document.getElementById("third-"  + key) || {}).value || "";
    winner = winner.trim(); second = second.trim(); third = third.trim();
    if (!winner) return;
    raceResults[key] = { winner: winner, second: second, third: third };
    renderResultFooter(track, raceNumber);
    fetch(API + "/api/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track: track, race_number: raceNumber, winner: winner, second: second, third: third })
    }).catch(function() {});
}

function renderResultFooter(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var footer = document.getElementById("result-footer-" + key);
    if (!footer) return;
    var result = getResult(track, raceNumber);
    if (result) {
        footer.innerHTML =
            '<div class="result-display">' +
            '<span class="result-label">Result</span>' +
            '<span class="result-winner">🥇 ' + result.winner + '</span>' +
            (result.second ? '<span style="color:#c0c0c0">🥈 ' + result.second + '</span>' : '') +
            (result.third  ? '<span style="color:#cd7f32">🥉 ' + result.third  + '</span>' : '') +
            '<button class="result-enter-btn" onclick="showResultInput(\'' + track + '\',' + raceNumber + ')">Edit</button>' +
            '</div>';
    } else {
        footer.innerHTML =
            '<div class="result-display">' +
            '<span class="result-label">Result</span>' +
            '<span style="color:#555">Not entered yet</span>' +
            '<button class="result-enter-btn" onclick="showResultInput(\'' + track + '\',' + raceNumber + ')">+ Enter Result</button>' +
            '</div>';
    }
}

function renderRaceCards() {
    var container    = document.getElementById("race-cards-container");
    var ratingFilter = document.getElementById("filter-rating").value;
    var trackFilter  = document.getElementById("filter-track").value;
    var sortBy       = document.getElementById("filter-sort").value;

    var raceMap = {};
    for (var i = 0; i < allOverlays.length; i++) {
        var o = allOverlays[i];
        var key = o.track + "_" + o.race_number;
        if (!raceMap[key]) raceMap[key] = {
            track: o.track, race_number: o.race_number,
            race_time: o.race_time, race_name: o.race_name || "", runners: []
        };
        raceMap[key].runners.push(o);
    }

    var keys = Object.keys(raceMap);
    for (var i = 0; i < keys.length; i++) {
        raceMap[keys[i]].runners.sort(function(a, b) {
            if (sortBy === "overlay_score") return (b.overlay_score||0) - (a.overlay_score||0);
            if (sortBy === "track_wins") return parseFloat(b.track_wins||0) - parseFloat(a.track_wins||0);
            return (b.fair_value||0) - (a.fair_value||0);
        });
    }

    var sortedRaces = Object.values(raceMap).sort(function(a, b) {
        var sa = secondsUntil(a.race_time); if (sa === null) sa = 9999;
        var sb = secondsUntil(b.race_time); if (sb === null) sb = 9999;
        return sa - sb;
    });

    var filtered = sortedRaces.filter(function(race) {
        if (trackFilter !== "ALL" && race.track !== trackFilter) return false;
        if (ratingFilter !== "ALL") return race.runners.some(function(r) { return r.rating === ratingFilter; });
        return true;
    });

    if (!filtered.length) {
        container.innerHTML = '<p class="loading">No races found for current filters.</p>';
        return;
    }

    var html = "";
    for (var i = 0; i < filtered.length; i++) {
        var race     = filtered[i];
        var secs     = secondsUntil(race.race_time);
        var resulted = isResulted(race.race_time);
        var timerCls = resulted ? "resulted" : timerClass(secs !== null ? secs : 9999);
        var timerTxt = resulted ? "Resulted" : (secs !== null ? formatCountdown(secs) : race.race_time);
        var raceKey  = resultKey(race.track, race.race_number);
        var result   = getResult(race.track, race.race_number);

        var runners = ratingFilter === "ALL" ? race.runners :
            race.runners.filter(function(r) { return r.rating === ratingFilter; });

        var rows = "";
        for (var j = 0; j < runners.length; j++) {
            var o = runners[j];
            var rankClass   = j===0?"rank-1":j===1?"rank-2":j===2?"rank-3":"";
            var badgeClass  = j===0?"r1":j===1?"r2":j===2?"r3":"rn";
            var isWinner    = result && result.winner && result.winner.toLowerCase() === (o.horse_name||"").toLowerCase();
            var winStyle    = isWinner ? 'style="background:#1a2010;border-left:3px solid #2a9d8f"' : '';
            rows +=
                '<tr class="' + rankClass + '" ' + winStyle + '>' +
                '<td><span class="rank-badge ' + badgeClass + '">' + (j+1) + '</span></td>' +
                '<td><strong>' + o.horse_name + '</strong>' + (isWinner ? ' ✅' : '') + '</td>' +
                '<td>' + (o.barrier !== null && o.barrier !== undefined ? o.barrier : '--') + '</td>' +
                '<td class="col-jockey">' + (o.jockey||'--') + '</td>' +
                '<td><span class="form-string">' + formatForm(o.form_string||'') + '</span></td>' +
                '<td class="col-career ' + statClass(o.career_wins) + '">' + (o.career_wins||'--') + '</td>' +
                '<td class="' + statClass(o.track_wins) + '">' + (o.track_wins||'--') + '</td>' +
                '<td class="col-dist ' + statClass(o.dist_wins) + '">' + (o.dist_wins||'--') + '</td>' +
                '<td><strong>' + (o.fair_value!=null ? o.fair_value.toFixed(1)+'%' : '--') + '</strong></td>' +
                '<td class="fair-odds">' + (o.est_fair_odds!=null ? '$'+o.est_fair_odds.toFixed(2) : '--') + '</td>' +
                '<td class="col-tote">' + (o.tote_odds>0 ? '$'+o.tote_odds.toFixed(2) : '--') + '</td>' +
                '<td class="col-overlay ' + ((o.overlay_score||0)>0?'score-positive':'score-negative') + '">' +
                    (o.overlay_score!=null && o.tote_odds>0 ? o.overlay_score.toFixed(2) : '--') + '</td>' +
                '<td><span class="badge ' + (o.rating||'NONE').replace('/','') + '">' + (o.rating||'NONE') + '</span></td>' +
                '</tr>';
        }

        var resultFooter = resulted ?
            '<div id="result-footer-' + raceKey + '"></div>' : '';

        html +=
            '<div class="race-block' + (resulted?' resulted-race':'') + '">' +
            '<div class="race-block-header">' +
            '<span class="race-block-title">' + race.track + ' — Race ' + race.race_number + '</span>' +
            '<span class="race-block-meta">' + race.race_name + ' &nbsp;·&nbsp; ' + race.race_time + '</span>' +
            '<span class="race-timer ' + timerCls + '" data-time="' + race.race_time + '">' + timerTxt + '</span>' +
            '</div>' +
            '<div class="table-wrapper"><table>' +
            '<thead><tr><th>#</th><th>Horse</th><th>Bar</th><th class="col-jockey">Jockey</th>' +
            '<th>Form</th><th class="col-career">Career W%</th><th>Track W%</th>' +
            '<th class="col-dist">Dist W%</th><th>Fair Value %</th><th>Fair Odds</th>' +
            '<th class="col-tote">Tote</th><th class="col-overlay">Overlay</th><th>Rating</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div>' +
            resultFooter +
            '</div>';
    }

    container.innerHTML = html;

    for (var i = 0; i < filtered.length; i++) {
        if (isResulted(filtered[i].race_time)) {
            renderResultFooter(filtered[i].track, filtered[i].race_number);
        }
    }
}

function formatForm(form) {
    var out = "";
    for (var i = 0; i < form.length; i++) {
        var ch = form[i];
        if (ch === "1") out += '<span class="form-win">' + ch + '</span>';
        else if (ch === "2" || ch === "3") out += '<span class="form-place">' + ch + '</span>';
        else if (ch >= "4" && ch <= "9") out += '<span class="form-miss">' + ch + '</span>';
        else out += ch;
    }
    return out;
}

function statClass(val) {
    if (!val) return "";
    var n = parseFloat(val);
    if (n >= 30) return "stat-high";
    if (n >= 15) return "stat-mid";
    return "stat-low";
}

function updateSummaryCards() {
    var strong = 0, good = 0;
    for (var i = 0; i < allOverlays.length; i++) {
        if (allOverlays[i].rating === "STRONG") strong++;
        if (allOverlays[i].rating === "GOOD") good++;
    }
    document.getElementById("runners-count").textContent = allOverlays.length;
    document.getElementById("strong-count").textContent  = strong;
    document.getElementById("good-count").textContent    = good;
    renderBestBets();
}

function renderBestBets() {
    var section = document.getElementById("best-bets-section");
    var grid    = document.getElementById("best-bets-grid");
    if (!allOverlays.length) { section.style.display = "none"; return; }

    var seen = {};
    var top5 = [];
    var sorted = allOverlays.slice().sort(function(a,b) { return (b.fair_value||0)-(a.fair_value||0); });

    for (var i = 0; i < sorted.length; i++) {
        var o = sorted[i];
        var k = o.track + "_" + o.race_number;
        if (seen[k]) continue;
        if (isResulted(o.race_time)) continue;
        seen[k] = true;
        top5.push(o);
        if (top5.length === 5) break;
    }

    if (!top5.length) { section.style.display = "none"; return; }
    section.style.display = "block";

    var rankLabels  = ["🥇 Top Pick","🥈 2nd Pick","🥉 3rd Pick","4th Pick","5th Pick"];
    var rankClasses = ["rank-1","rank-2","rank-3","rank-4","rank-5"];

    var html = "";
    for (var i = 0; i < top5.length; i++) {
        var o      = top5[i];
        var secs   = secondsUntil(o.race_time);
        var tTxt   = secs !== null ? formatCountdown(secs) : o.race_time;
        var tCls   = timerClass(secs !== null ? secs : 9999);
        var fvCls  = (o.fair_value||0)>=20?"good":(o.fair_value||0)>=12?"warn":"";
        var twCls  = parseFloat(o.track_wins||0)>=25?"good":parseFloat(o.track_wins||0)>=12?"warn":"";
        html +=
            '<div class="bet-card ' + rankClasses[i] + '">' +
            '<div class="bet-card-rank">' + rankLabels[i] + '</div>' +
            '<div class="bet-card-horse">' + o.horse_name + '</div>' +
            '<div class="bet-card-race">' + o.track + ' R' + o.race_number + ' <span>· ' + o.race_time + '</span></div>' +
            '<div class="bet-card-stats">' +
            '<div class="bet-stat"><div class="bet-stat-label">Fair Value</div>' +
            '<div class="bet-stat-value ' + fvCls + '">' + (o.fair_value!=null?o.fair_value.toFixed(1)+'%':'--') + '</div></div>' +
            '<div class="bet-stat"><div class="bet-stat-label">Fair Odds</div>' +
            '<div class="bet-stat-value">' + (o.est_fair_odds!=null?'$'+o.est_fair_odds.toFixed(2):'--') + '</div></div>' +
            '<div class="bet-stat"><div class="bet-stat-label">Track W%</div>' +
            '<div class="bet-stat-value ' + twCls + '">' + (o.track_wins||'--') + '</div></div>' +
            '<div class="bet-stat"><div class="bet-stat-label">Dist W%</div>' +
            '<div class="bet-stat-value">' + (o.dist_wins||'--') + '</div></div>' +
            '</div>' +
            '<div class="bet-card-footer">' +
            '<span class="bet-form">' + formatForm(o.form_string||'') + '</span>' +
            '<span class="bet-timer ' + tCls + '" data-time="' + o.race_time + '">' + tTxt + '</span>' +
            '</div></div>';
    }
    grid.innerHTML = html;
}

function renderWeather(weather) {
    var grid    = document.getElementById("weather-grid");
    var entries = Object.values(weather);
    if (!entries.length) { grid.innerHTML = '<p class="loading">No weather data.</p>'; return; }
    var html = "";
    for (var i = 0; i < entries.length; i++) {
        var w = entries[i];
        html += '<div class="weather-card"><h3>' + w.track + '</h3>' +
            '<p>🌡️ <span>' + w.temperature + '°C</span></p>' +
            '<p>💧 <span>' + w.humidity + '%</span></p>' +
            '<p>💨 <span>' + w.wind_speed + ' km/h</span></p>' +
            '<p>☁️ <span>' + w.conditions + '</span></p></div>';
    }
    grid.innerHTML = html;
}

function populateTrackFilter() {
    var select  = document.getElementById("filter-track");
    var current = select.value;
    var tracks  = [];
    var seen    = {};
    for (var i = 0; i < allOverlays.length; i++) {
        var t = allOverlays[i].track;
        if (t && !seen[t]) { seen[t] = true; tracks.push(t); }
    }
    var html = '<option value="ALL">All Tracks</option>';
    for (var i = 0; i < tracks.length; i++) {
        html += '<option value="' + tracks[i] + '"' + (tracks[i]===current?' selected':'') + '>' + tracks[i] + '</option>';
    }
    select.innerHTML = html;
}

function setUpdated(ts) {
    document.getElementById("last-updated").textContent =
        "Updated: " + new Date(ts).toLocaleTimeString();
}

function setStatus(color, text) {
    document.getElementById("status-dot").className = "dot " + color;
    document.getElementById("status-text").textContent = text;
}