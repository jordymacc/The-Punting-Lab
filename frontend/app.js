const API = "https://punting-lab-backend.onrender.com";
let allOverlays = [];
let allRaces = [];
let ws = null;
let countdownInterval = null;
let raceResults = {};
let virtualScroll = null;

document.addEventListener("DOMContentLoaded", function() {
    virtualScroll = new VirtualScroll("race-cards-container", {
        itemHeight: 160,
        rowHeight: 42,
        buffer: 5,
        threshold: 15,
        minItems: 3,
        maxItems: 150
    });
    window.virtualScroll = virtualScroll;

    loadResultsFromDB();
    fetchData();
    connectWebSocket();
    setInterval(fetchData, 60000);
    startCountdownTick();

    document.getElementById("filter-rating").addEventListener("change", applyFilters);
    document.getElementById("filter-track").addEventListener("change", applyFilters);
    document.getElementById("filter-sort").addEventListener("change", applyFilters);
});

function connectWebSocket() {
    var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    var wsUrl = protocol + "//" + API.replace(/^https?:\/\//, "") + "/ws";
    try {
        ws = new WebSocket(wsUrl);
        ws.onopen = function() {
            setStatus("green", "Live");
            ws.send("ping");
        };
        ws.onmessage = function(ev) {
            try {
                var msg = JSON.parse(ev.data);
                if (msg.type === "result_saved" || msg.type === "init") {
                    loadResultsFromDB();
                }
            } catch (e) {}
        };
        ws.onclose = function() {
            setStatus("red", "Offline");
            setTimeout(connectWebSocket, 5000);
        };
        ws.onerror = function() {
            setStatus("red", "Error");
        };
    } catch (e) {
        console.error("WS error:", e);
    }
}

function fetchData() {
    fetch(API + "/api/overlays")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            allOverlays = data.overlays || [];
            applyFilters();
            updateSummaryCards();
            populateTrackFilter();
            if (data.last_updated) setUpdated(data.last_updated);
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
        .then(function(d) {
            allRaces = d.races || [];
            updateNextRaceBanner();
        })
        .catch(function() {});
}

function applyFilters() {
    var ratingFilter = document.getElementById("filter-rating").value;
    var trackFilter  = document.getElementById("filter-track").value;
    var sortBy       = document.getElementById("filter-sort").value;

    var filtered = allOverlays.filter(function(o) {
        if (trackFilter !== "ALL" && o.track !== trackFilter) return false;
        if (ratingFilter !== "ALL") return o.rating === ratingFilter;
        return true;
    });

    if (sortBy === "fair_value") {
        filtered.sort(function(a, b) { return (b.fair_value || 0) - (a.fair_value || 0); });
    } else if (sortBy === "overlay_score") {
        filtered.sort(function(a, b) { return (b.overlay_score || 0) - (a.overlay_score || 0); });
    } else if (sortBy === "track_wins") {
        filtered.sort(function(a, b) { return parseFloat(b.track_wins || 0) - parseFloat(a.track_wins || 0); });
    } else {
        filtered.sort(function(a, b) {
            var sa = secondsUntil(a.race_time), sb = secondsUntil(b.race_time);
            return (sa === null ? 9999 : sa) - (sb === null ? 9999 : sb);
        });
    }

    if (virtualScroll) {
        virtualScroll.setData(filtered);
    }
}

function loadResultsFromDB() {
    fetch(API + "/api/results")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            raceResults = {};
            var results = data.results || [];
            for (var i = 0; i < results.length; i++) {
                var r = results[i];
                var key = r.track + "_" + r.race_number;
                raceResults[key] = { winner: r.winner, second: r.second, third: r.third };
            }
            if (virtualScroll && allOverlays.length > 0) {
                virtualScroll.raceResults = raceResults;
                applyFilters();
            }
        })
        .catch(function() {});
}

function submitResult(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var winner = (document.getElementById("winner-" + key) || {}).value || "";
    var second = (document.getElementById("second-" + key) || {}).value || "";
    var third  = (document.getElementById("third-"  + key) || {}).value || "";
    winner = winner.trim(); second = second.trim(); third = third.trim();
    if (!winner) return;

    raceResults[key] = { winner: winner, second: second, third: third };

    fetch(API + "/api/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track: track, race_number: raceNumber, winner: winner, second: second, third: third })
    }).then(function() {
        var footer = document.getElementById("result-footer-" + key);
        if (footer) footer.remove();
        applyFilters();
    }).catch(function() {});
}

function showResultInput(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var existing = document.getElementById("result-footer-" + key);
    if (existing) return;

    var items = document.querySelectorAll(".virtual-scroll-item");
    var found = null;
    for (var i = 0; i < items.length; i++) {
        var header = items[i].querySelector(".race-block-title");
        if (header && header.textContent.indexOf(track + " \u2014 Race " + raceNumber) > -1) {
            found = items[i];
            break;
        }
    }
    if (!found) return;

    var div = document.createElement("div");
    div.id = "result-footer-" + key;
    div.className = "result-input-row";
    div.innerHTML = '<input class="result-input" id="winner-' + key + '" placeholder="1st place..." />' +
        '<input class="result-input" id="second-' + key + '" placeholder="2nd..." style="max-width:120px"/>' +
        '<input class="result-input" id="third-' + key + '" placeholder="3rd..." style="max-width:120px"/>' +
        '<button class="result-save-btn" onclick="submitResult(\'' + track + '\', ' + raceNumber + ')">Save</button>' +
        '<button class="result-cancel-btn" onclick="cancelResult(\'' + track + '\', ' + raceNumber + ')">\u00d7</button>';
    found.appendChild(div);
    var inp = document.getElementById("winner-" + key);
    if (inp) inp.focus();
}

function cancelResult(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var footer = document.getElementById("result-footer-" + key);
    if (footer) footer.remove();
}

function resultKey(track, raceNumber) {
    return track.replace(/\s+/g, "_") + "_" + raceNumber;
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

    var rankLabels  = ["\ud83e\udd47 Top Pick","\ud83e\udd48 2nd Pick","\ud83e\udd49 3rd Pick","4th Pick","5th Pick"];
    var rankClasses = ["rank-1","rank-2","rank-3","rank-4","rank-5"];

    var html = "";
    for (var i = 0; i < top5.length; i++) {
        var o      = top5[i];
        var secs   = secondsUntil(o.race_time);
        var tTxt   = secs !== null ? formatCountdown(secs) : o.race_time;
        var tCls   = timerClass(secs !== null ? secs : 9999);
        var fvCls  = (o.fair_value||0)>=20?"good":(o.fair_value||0)>=12?"warn":"";
        var twCls  = parseFloat(o.track_wins||0)>=25?"good":parseFloat(o.track_wins||0)>=12?"warn":"";

        html += '<div class="bet-card ' + rankClasses[i] + '">' +
            '<div class="bet-card-rank">' + rankLabels[i] + '</div>' +
            '<div class="bet-card-horse">' + o.horse_name + '</div>' +
            '<div class="bet-card-race">' + o.track + ' R' + o.race_number + ' <span>\u00b7 ' + o.race_time + '</span></div>' +
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

function updateNextRaceBanner() {
    var banner = document.getElementById("next-race-banner");
    var nameEl = document.getElementById("next-race-name");
    if (!allRaces.length) { banner.style.display = "none"; return; }

    var upcoming = allRaces.filter(function(r) {
        return !isResulted(r.race_time);
    }).sort(function(a,b) {
        return secondsUntil(a.race_time) - secondsUntil(b.race_time);
    });

    if (!upcoming.length) { banner.style.display = "none"; return; }
    banner.style.display = "block";
    var next = upcoming[0];
    nameEl.textContent = next.track + " R" + next.race_number;
}

function renderWeather(weather) {
    var grid = document.getElementById("weather-grid");
    var entries = Object.values(weather);
    if (!entries.length) { grid.innerHTML = '<p class="loading">No weather data.</p>'; return; }

    var html = "";
    for (var i = 0; i < entries.length; i++) {
        var w = entries[i];
        html += '<div class="weather-card"><h3>' + w.track + '</h3>' +
            '<p>\ud83c\udf21\ufe0f <span>' + w.temperature + '\u00b0C</span></p>' +
            '<p>\ud83d\udca7 <span>' + w.humidity + '%</span></p>' +
            '<p>\ud83d\udca8 <span>' + w.wind_speed + ' km/h</span></p>' +
            '<p>\u2601\ufe0f <span>' + w.conditions + '</span></p></div>';
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

function loadAccuracy() {
    fetch(API + "/api/accuracy")
        .then(function(r) { return r.json(); })
        .then(function(d) {
            var section = document.getElementById("accuracy-section");
            if (!d.total) { section.style.display = "none"; return; }
            section.style.display = "block";
            document.getElementById("acc-total").textContent = d.total;
            document.getElementById("acc-wins").textContent = d.wins;
            document.getElementById("acc-winrate").textContent = d.win_rate + "%";
            document.getElementById("acc-placerate").textContent = d.place_rate + "%";
        })
        .catch(function() {});
}

function secondsUntil(timeStr) {
    if (!timeStr) return null;
    var now = new Date();
    var parts = timeStr.split(":");
    var h = parseInt(parts[0]), m = parseInt(parts[1]);
    var raceTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);
    var diff = (raceTime - now) / 1000;
    return diff > -300 ? diff : null;
}

function isResulted(timeStr) {
    var s = secondsUntil(timeStr);
    return s !== null && s < -2700;
}

function formatCountdown(secs) {
    if (secs <= 0) return "LIVE";
    var h = Math.floor(secs / 3600);
    var m = Math.floor((secs % 3600) / 60);
    var s = Math.floor(secs % 60);
    if (h > 0) return h + "h " + (m < 10 ? "0" : "") + m + "m";
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
}

function timerClass(secs) {
    if (secs <= 0) return "live";
    if (secs < 600) return "urgent";
    if (secs < 3600) return "soon";
    return "";
}

function formatForm(form) {
    if (!form) return "";
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

function setUpdated(ts) {
    document.getElementById("last-updated").textContent = "Updated: " + new Date(ts).toLocaleTimeString();
}

function setStatus(color, text) {
    document.getElementById("status-dot").className = "dot " + color;
    document.getElementById("status-text").textContent = text;
}

function startCountdownTick() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(function() {
        var timers = document.querySelectorAll("[data-time]");
        for (var i = 0; i < timers.length; i++) {
            var el = timers[i];
            var secs = secondsUntil(el.getAttribute("data-time"));
            if (secs === null) { el.textContent = "--"; continue; }
            el.textContent = formatCountdown(secs);
            el.className = el.className.replace(/\b(urgent|soon|live)\b/g, "").trim() + " " + timerClass(secs);
        }
    }, 1000);
}

window.addEventListener("beforeunload", function() {
    if (virtualScroll) virtualScroll.destroy();
    if (ws) ws.close();
    if (countdownInterval) clearInterval(countdownInterval);
});