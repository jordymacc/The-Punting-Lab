const API = "https://punting-lab-backend.onrender.com";
let allOverlays = [];
let allRaces = [];
let ws = null;
let countdownInterval = null;
// Add at top of app.js after const API = ...
let raceResults = {}; // Store results here for virtual scroll access

document.addEventListener("DOMContentLoaded", function() {
    // Initialize virtual scroll
    const virtualScroll = new VirtualScroll('race-cards-container', {
        itemHeight: 142,  // Header (36px) + Table (~80-100px per race)
        rowHeight: 42,    // Each horse row height
        buffer: 5,
        threshold: 15,     // Load more when scrolled this far from bottom
        minItems: 3,
        maxItems: 150      // Cap at 150 items for performance
    });

    // Store reference globally for access in callbacks
    window.virtualScroll = virtualScroll;

    loadResultsFromDB();
    fetchData();
    connectWebSocket();
    setInterval(fetchData, 60000);
    startCountdownTick();
    
    document.getElementById("filter-rating").addEventListener("change", renderRaceCards);
    document.getElementById("filter-track").addEventListener("change", renderRaceCards);
    document.getElementById("filter-sort").addEventListener("change", renderRaceCards);

    // Set initial data when overlays load
    if (allOverlays.length > 0) {
        virtualScroll.setData(allOverlays);
    } else {
        // Fallback to old method for empty state
        renderRaceCards();
    }
});

// Override fetchData to update virtual scroll
function fetchData() {
    fetch(API + "/api/overlays")
        .then(function(r) { return r.json(); })
        .then(function(overlayData) {
            allOverlays = overlayData.overlays || [];
            
            // Update virtual scroll with new data
            if (allOverlays.length > 0) {
                virtualScroll.setData(allOverlays);
            } else {
                renderRaceCards(); // Fallback for empty state
            }

            updateSummaryCards();
            populateTrackFilter();
            if (overlayData.last_updated) setUpdated(overlayData.last_updated);
            setStatus("green", "Live");
        })
        .catch(function() { 
            setStatus("red", "Offline"); 
            renderRaceCards(); // Fallback on error
        });

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

// Override renderRaceCards to work with virtual scroll
function renderRaceCards() {
    var container    = document.getElementById("race-cards-container");
    var ratingFilter = document.getElementById("filter-rating").value;
    var trackFilter  = document.getElementById("filter-track").value;
    var sortBy       = document.getElementById("filter-sort").value;

    // Filter and sort overlays based on current filters
    var filteredOverlays = allOverlays.filter(function(o) {
        if (trackFilter !== "ALL" && o.track !== trackFilter) return false;
        if (ratingFilter !== "ALL") return o.rating === ratingFilter;
        return true;
    });

    // Sort by race time
    filteredOverlays.sort(function(a, b) {
        var sa = secondsUntil(a.race_time); 
        var sb = secondsUntil(b.race_time); 
        if (sa === null) sa = 9999;
        if (sb === null) sb = 9999;
        return sa - sb;
    });

    // Update virtual scroll with filtered data
    virtualScroll.setData(filteredOverlays);
}

// Override loadResultsFromDB to update raceResults for virtual scroll
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
            
            // Re-render virtual scroll to show result highlights
            if (virtualScroll && allOverlays.length > 0) {
                virtualScroll.setData(allOverlays);
            } else {
                renderRaceCards(); // Fallback
            }
        })
        .catch(function() {});
}

// Override submitResult to update raceResults and re-render
function submitResult(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var winner = (document.getElementById("winner-" + key) || {}).value || "";
    var second = (document.getElementById("second-" + key) || {}).value || "";
    var third  = (document.getElementById("third-"  + key) || {}).value || "";
    winner = winner.trim(); second = second.trim(); third = third.trim();
    
    if (!winner) return;
    
    raceResults[key] = { winner: winner, second: second, third: third };
    
    // Re-render virtual scroll to show result highlights
    if (virtualScroll && allOverlays.length > 0) {
        virtualScroll.setData(allOverlays);
    } else {
        renderRaceCards(); // Fallback
    }

    fetch(API + "/api/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track: track, race_number: raceNumber, winner: winner, second: second, third: third })
    }).catch(function() {});
}

// Override renderResultFooter to work with virtual scroll
function renderResultFooter(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    
    // The footer is now rendered inside each virtual item automatically
    // No need for separate footer rendering
    
    return true; // Success indicator
}

// Override showResultInput to work with virtual scroll
function showResultInput(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    
    // Find the virtual item for this race and append footer
    const items = document.querySelectorAll('.virtual-scroll-item');
    let foundItem = null;
    
    for (let i = 0; i < items.length; i++) {
        const header = items[i].querySelector('.race-block-header');
        if (header) {
            const title = header.querySelector('.race-block-title').textContent;
            if (title.includes(track + ' — Race ' + raceNumber)) {
                foundItem = items[i];
                break;
            }
        }
    }
    
    if (!foundItem) return;

    // Append result input row to the item
    const footerDiv = document.createElement('div');
    footerDiv.id = "result-footer-" + key;
    footerDiv.innerHTML = `
        <div class="result-input-row">
            <input class="result-input" id="winner-${key}" placeholder="1st place..." />
            <input class="result-input" id="second-${key}" placeholder="2nd..." style="max-width:120px"/>
            <input class="result-input" id="third-${key}" placeholder="3rd..." style="max-width:120px"/>
            <button class="result-save-btn" onclick="submitResult('${track}', ${raceNumber})">Save</button>
            <button class="result-cancel-btn" onclick="renderResultFooter('${track}', ${raceNumber})">×</button>
        </div>`;

    foundItem.appendChild(footerDiv);
    
    const inp = document.getElementById("winner-" + key);
    if (inp) inp.focus();
}

// Override renderResultFooter to clear input when closed
function renderResultFooter(track, raceNumber) {
    var key = resultKey(track, raceNumber);
    var footer = document.getElementById("result-footer-" + key);
    
    if (!footer) return;
    
    // Clear inputs and remove footer
    const inputs = footer.querySelectorAll('input');
    inputs.forEach(input => input.value = '');
    
    footer.remove();
}

// Override updateSummaryCards to work with virtual scroll
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

// Override renderBestBets to work with virtual scroll
function renderBestBets() {
    var section = document.getElementById("best-bets-section");
    var grid    = document.getElementById("best-bets-grid");
    
    if (!allOverlays.length) { 
        section.style.display = "none"; 
        return; 
    }

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
        
        html += `
            <div class="bet-card ${rankClasses[i]}">
                <div class="bet-card-rank">${rankLabels[i]}</div>
                <div class="bet-card-horse">${o.horse_name}</div>
                <div class="bet-card-race">${o.track} R${o.race_number} <span>· ${o.race_time}</span></div>
                <div class="bet-card-stats">
                    <div class="bet-stat"><div class="bet-stat-label">Fair Value</div>
                    <div class="bet-stat-value ${fvCls}">${o.fair_value!=null?o.fair_value.toFixed(1)+'%':'--'}</div></div>
                    <div class="bet-stat"><div class="bet-stat-label">Fair Odds</div>
                    <div class="bet-stat-value">${o.est_fair_odds!=null?'$'+o.est_fair_odds.toFixed(2):'--'}</div></div>
                    <div class="bet-stat"><div class="bet-stat-label">Track W%</div>
                    <div class="bet-stat-value ${twCls}">${o.track_wins||'--'}</div></div>
                    <div class="bet-stat"><div class="bet-stat-label">Dist W%</div>
                    <div class="bet-stat-value">${o.dist_wins||'--'}</div></div>
                </div>
                <div class="bet-card-footer">
                    <span class="bet-form">${formatForm(o.form_string||'')}</span>
                    <span class="bet-timer ${tCls}" data-time="${o.race_time}">${tTxt}</span>
                </div></div>`;
    }
    
    grid.innerHTML = html;
}

// Override renderWeather to work with virtual scroll (no changes needed)
function renderWeather(weather) {
    var grid    = document.getElementById("weather-grid");
    var entries = Object.values(weather);
    if (!entries.length) { grid.innerHTML = '<p class="loading">No weather data.</p>'; return; }
    
    var html = "";
    for (var i = 0; i < entries.length; i++) {
        var w = entries[i];
        html += `<div class="weather-card"><h3>${w.track}</h3>
            <p>🌡️ <span>${w.temperature}°C</span></p>
            <p>💧 <span>${w.humidity}%</span></p>
            <p>💨 <span>${w.wind_speed} km/h</span></p>
            <p>☁️ <span>${w.conditions}</span></p></div>`;
    }
    
    grid.innerHTML = html;
}

// Override populateTrackFilter to work with virtual scroll (no changes needed)
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
        html += `<option value="${tracks[i]}"${tracks[i]===current?' selected':''}>${tracks[i]}</option>`;
    }
    
    select.innerHTML = html;
}

// Override setUpdated to work with virtual scroll (no changes needed)
function setUpdated(ts) {
    document.getElementById("last-updated").textContent = "Updated: " + new Date(ts).toLocaleTimeString();
}

// Override setStatus to work with virtual scroll (no changes needed)
function setStatus(color, text) {
    document.getElementById("status-dot").className = "dot " + color;
    document.getElementById("status-text").textContent = text;
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (virtualScroll) {
        virtualScroll.destroy();
    }
});
let raceResults = {};

