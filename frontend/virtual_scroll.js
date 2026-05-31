/**
 * Virtual Scroll Component - Renders only visible race cards efficiently
 */
class VirtualScroll {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            itemHeight: 160,
            rowHeight: 42,
            buffer: 5,
            threshold: 100,
            minItems: 3,
            maxItems: 200,
            ...options
        };

        this.items = [];
        this.visibleStart = 0;
        this.visibleEnd = 0;
        this.scrollContainer = null;
        this.renderedItems = new Map();
        this.raceResults = {};   // synced from app.js

        this.init();
    }

    init() {
        if (!this.container) return;

        this.scrollContainer = document.createElement("div");
        this.scrollContainer.className = "virtual-scroll-container";
        this.scrollContainer.style.height = "600px";
        this.scrollContainer.style.overflowY = "auto";
        this.scrollContainer.style.position = "relative";

        this.container.innerHTML = "";
        this.container.appendChild(this.scrollContainer);

        var self = this;
        var ticking = false;
        this.scrollContainer.addEventListener("scroll", function() {
            if (!ticking) {
                window.requestAnimationFrame(function() {
                    self.handleScroll();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }

    setData(items) {
        if (!Array.isArray(items)) return;
        var limited = items.slice(0, this.options.maxItems);
        this.items = limited.map(function(item, index) {
            return { id: item.track + "_" + item.race_number, data: item, index: index };
        });
        this.scrollContainer.scrollTop = 0;
        this.visibleStart = 0;
        this.visibleEnd = Math.min(this.items.length - 1, 20);
        this.render();
    }

    handleScroll() {
        var scrollTop = this.scrollContainer.scrollTop;
        var viewportHeight = this.scrollContainer.clientHeight;
        this.visibleStart = Math.floor(scrollTop / this.options.itemHeight);
        this.visibleEnd = Math.min(
            this.items.length - 1,
            Math.ceil((scrollTop + viewportHeight) / this.options.itemHeight)
        );
        this.render();
    }

    render() {
        // Clear old items
        var existing = this.scrollContainer.querySelectorAll(".virtual-scroll-item");
        for (var i = 0; i < existing.length; i++) {
            existing[i].remove();
        }
        this.renderedItems.clear();

        var scrollTop = this.scrollContainer.scrollTop;
        var startOffset = Math.max(0, Math.floor(scrollTop / this.options.itemHeight) - this.options.buffer);
        var endOffset = Math.min(
            this.items.length - 1,
            Math.ceil((scrollTop + this.scrollContainer.clientHeight) / this.options.itemHeight) + this.options.buffer
        );

        for (var i = startOffset; i <= endOffset; i++) {
            if (i >= this.items.length || i < 0) continue;
            this.renderItem(this.items[i], i);
        }
    }

    renderItem(item, index) {
        var key = String(index);
        if (this.renderedItems.has(key)) return;

        var el = document.createElement("div");
        el.className = "virtual-scroll-item";
        el.style.position = "absolute";
        el.style.top = (index * this.options.itemHeight) + "px";
        el.style.left = "0";
        el.style.right = "0";
        el.style.height = this.options.itemHeight + "px";
        el.dataset.index = index;

        this.renderItemContent(item.data, el);
        this.renderedItems.set(key, el);
        this.scrollContainer.appendChild(el);
    }

    renderItemContent(data, container) {
        var raceKey = data.track + "_" + data.race_number;
        var result = this.raceResults[raceKey] || null;
        var resulted = isResulted(data.race_time);

        // Header
        var header = document.createElement("div");
        header.className = "race-block-header";
        var secs = secondsUntil(data.race_time);
        var timerText = secs !== null ? formatCountdown(secs) : data.race_time;
        var timerClassName = timerClass(secs !== null ? secs : 9999);
        header.innerHTML = '<span class="race-block-title">' + data.track + " \u2014 Race " + data.race_number + '</span>' +
            '<span class="race-block-meta">' + (data.race_name || "") + '</span>' +
            '<span class="race-timer ' + timerClassName + '" data-time="' + data.race_time + '">' + timerText + '</span>';
        container.appendChild(header);

        // Table wrapper
        var tableWrapper = document.createElement("div");
        tableWrapper.className = "table-wrapper";

        var table = document.createElement("table");
        var thead = document.createElement("thead");
        thead.innerHTML = '<tr>' +
            '<th>#</th><th>Horse</th><th>Bar</th><th class="col-jockey">Jockey</th>' +
            '<th>Form</th><th class="col-career">Career W%</th><th>Track W%</th>' +
            '<th class="col-dist">Dist W%</th><th>Fair Value %</th><th>Fair Odds</th>' +
            '<th class="col-tote">Tote</th><th class="col-overlay">Overlay</th><th>Rating</th>' +
            '</tr>';
        table.appendChild(thead);

        var tbody = document.createElement("tbody");
        var runners = data.runners || [];
        var ratingFilter = document.getElementById("filter-rating");
        var currentRating = ratingFilter ? ratingFilter.value : "ALL";

        if (currentRating !== "ALL") {
            runners = runners.filter(function(r) { return r.rating === currentRating; });
        }

        var maxRows = Math.min(runners.length, 10);
        for (var j = 0; j < maxRows; j++) {
            var runner = runners[j];
            if (!runner) continue;

            var row = document.createElement("tr");
            row.className = "rank-" + (j + 1);

            var winStyle = "";
            if (result && result.winner) {
                if (result.winner.toLowerCase() === (runner.horse_name || "").toLowerCase()) {
                    winStyle = ' style="background:#1a2010;border-left:3px solid #2a9d8f"';
                }
            }

            var statClass = function(val) {
                if (!val) return "";
                var n = parseFloat(val);
                if (n >= 30) return "stat-high";
                if (n >= 15) return "stat-mid";
                return "stat-low";
            };

            var formHtml = formatForm(runner.form_string || "");
            var fv = runner.fair_value != null ? runner.fair_value.toFixed(1) + "%" : "--";
            var eo = runner.est_fair_odds != null ? "$" + runner.est_fair_odds.toFixed(2) : "--";
            var tote = runner.tote_odds > 0 ? "$" + runner.tote_odds.toFixed(2) : "--";
            var os = runner.overlay_score != null && runner.tote_odds > 0 ? runner.overlay_score.toFixed(2) : "--";
            var osClass = (runner.overlay_score || 0) > 0 ? "score-positive" : "score-negative";
            var badgeClass = (runner.rating || "NONE").replace("/", "");

            row.innerHTML = '<td><span class="rank-badge rank-' + (j + 1) + '">' + (j + 1) + '</span></td>' +
                '<td><strong' + winStyle + '>' + (runner.horse_name || "Unknown") + '</strong>' + (winStyle ? " \u2705" : "") + '</td>' +
                '<td>' + (runner.barrier !== null && runner.barrier !== undefined ? runner.barrier : "--") + '</td>' +
                '<td class="col-jockey">' + (runner.jockey || "--") + '</td>' +
                '<td><span class="form-string">' + formHtml + '</span></td>' +
                '<td class="col-career ' + statClass(runner.career_wins) + '">' + (runner.career_wins || "--") + '</td>' +
                '<td class="' + statClass(runner.track_wins) + '">' + (runner.track_wins || "--") + '</td>' +
                '<td class="col-dist ' + statClass(runner.dist_wins) + '">' + (runner.dist_wins || "--") + '</td>' +
                '<td><strong>' + fv + '</strong></td>' +
                '<td class="fair-odds">' + eo + '</td>' +
                '<td class="col-tote">' + tote + '</td>' +
                '<td class="col-overlay ' + osClass + '">' + os + '</td>' +
                '<td><span class="badge ' + badgeClass + '">' + (runner.rating || "NONE") + '</span></td>';

            tbody.appendChild(row);
        }
        table.appendChild(tbody);
        tableWrapper.appendChild(table);
        container.appendChild(tableWrapper);

        // Result footer
        if (resulted) {
            var footerDiv = document.createElement("div");
            footerDiv.className = "result-display";
            if (result) {
                footerDiv.innerHTML = '<span class="result-label">Result</span>' +
                    '<span class="result-winner">\ud83c\udfc6 ' + result.winner + '</span>' +
                    (result.second ? '<span style="color:#c0c0c0">\ud83e\udd48 ' + result.second + '</span>' : "") +
                    (result.third ? '<span style="color:#cd7f32">\ud83e\udd49 ' + result.third + '</span>' : "") +
                    '<button class="result-enter-btn" onclick="showResultInput(\'' + data.track + '\', ' + data.race_number + ')">Edit</button>';
            } else {
                footerDiv.innerHTML = '<span class="result-label">Result</span>' +
                    '<span style="color:#555">Not entered yet</span>' +
                    '<button class="result-enter-btn" onclick="showResultInput(\'' + data.track + '\', ' + data.race_number + ')">+ Enter Result</button>';
            }
            container.appendChild(footerDiv);
        } else {
            // Add enter result button for non-resulted races
            var btnDiv = document.createElement("div");
            btnDiv.style.cssText = "padding:8px 16px;";
            btnDiv.innerHTML = '<button class="result-enter-btn" onclick="showResultInput(\'' + data.track + '\', ' + data.race_number + ')">+ Enter Result</button>';
            container.appendChild(btnDiv);
        }
    }

    destroy() {
        if (this.scrollContainer && this.scrollContainer.parentNode) {
            this.scrollContainer.parentNode.removeChild(this.scrollContainer);
        }
        this.renderedItems.clear();
        this.items = [];
    }
}

if (typeof window !== "undefined") {
    window.VirtualScroll = VirtualScroll;
}