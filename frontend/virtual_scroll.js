/**
 * Virtual Scroll Component - Renders only visible items efficiently
 */
class VirtualScroll {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            itemHeight: 80,           // Height of each race card (including header)
            rowHeight: 42,            // Height of each horse row in table
            buffer: 5,                // Extra items to render above/below viewport
            threshold: 100,          // Load more data when scrolled this far from bottom
            minItems: 3,              // Minimum items to always render
            maxItems: 200,           // Cap at this many items for performance
            ...options
        };

        this.items = [];             // Virtual list of all items
        this.visibleStart = 0;      // First visible item index
        this.visibleEnd = 0;        // Last visible item index
        
        this.scrollContainer = null;
        this.renderedItems = new Map(); // Cache rendered DOM elements
        this.observer = null;       // Intersection Observer for visibility tracking

        this.init();
    }

    init() {
        if (!this.container) return;

        // Create scroll container with fixed height
        this.scrollContainer = document.createElement('div');
        this.scrollContainer.className = 'virtual-scroll-container';
        this.scrollContainer.style.height = `${this.options.itemHeight}px`;
        this.scrollContainer.style.overflowY = 'auto';
        
        // Add scrollbar styling
        this.scrollContainer.style.scrollbarWidth = 'thin';  // Firefox
        this.scrollContainer.style.msOverflowStyle = 'scrollbar';  // IE/Edge
        
        // Replace container content
        this.container.innerHTML = '';
        this.container.appendChild(this.scrollContainer);

        // Attach scroll event listener with throttling
        let ticking = false;
        this.scrollContainer.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(() => {
                    this.handleScroll();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });

        // Load initial items
        this.loadItems(0, 10);
    }

    /**
     * Set the data to display
     */
    setData(items) {
        if (!Array.isArray(items)) return;

        // Limit max items for performance
        const limitedItems = items.slice(0, this.options.maxItems);
        
        this.items = limitedItems.map((item, index) => ({
            id: `${item.track}_${item.race_number}`,
            data: item,
            index: index
        }));

        // Reset scroll position to top
        this.scrollContainer.scrollTop = 0;
        this.visibleStart = 0;
        this.visibleEnd = Math.min(this.items.length - 1, this.options.itemHeight);

        // Render visible items
        this.render();
    }

    /**
     * Handle scroll events and update viewport
     */
    handleScroll() {
        const scrollTop = this.scrollContainer.scrollTop;
        const viewportHeight = this.scrollContainer.clientHeight;
        
        // Calculate visible range
        this.visibleStart = Math.floor(scrollTop / this.options.itemHeight);
        this.visibleEnd = Math.min(
            this.items.length - 1,
            Math.ceil((scrollTop + viewportHeight) / this.options.itemHeight)
        );

        // Load more items if near bottom
        const remainingItems = this.items.length - this.visibleEnd;
        if (remainingItems < this.options.threshold && remainingItems > 0) {
            this.loadMore();
        }

        // Render only changed items
        this.render();
    }

    /**
     * Load additional items from data source
     */
    async loadMore() {
        const nextIndex = this.visibleEnd + 1;
        
        if (nextIndex >= this.items.length) return;

        try {
            // Fetch remaining items in batches
            const batchSize = Math.min(20, this.items.length - nextIndex);
            const batchItems = this.items.slice(nextIndex, nextIndex + batchSize);
            
            // Render new items immediately (optimistic UI)
            this.renderBatch(batchItems);

        } catch (error) {
            console.error('Failed to load more items:', error);
        }
    }

    /**
     * Render a batch of items efficiently
     */
    renderBatch(items) {
        const scrollTop = this.scrollContainer.scrollTop;
        const viewportHeight = this.scrollContainer.clientHeight;
        
        // Calculate which items are visible in this batch
        const startOffset = Math.floor(scrollTop / this.options.itemHeight);
        const endOffset = Math.ceil((scrollTop + viewportHeight) / this.options.itemHeight);

        for (let i = 0; i < items.length; i++) {
            const itemIndex = nextIndex + i;
            
            if (itemIndex >= this.items.length) break;

            // Check if item is in viewport or near it
            const itemStart = startOffset + i;
            const itemEnd = itemStart + 1;

            if (itemEnd <= endOffset || itemStart >= endOffset - 2) {
                this.renderItem(items[i], itemIndex);
            }
        }
    }

    /**
     * Render a single item
     */
    renderItem(item, index) {
        const key = `${index}`;
        
        // Check if already rendered
        if (this.renderedItems.has(key)) return;

        // Create DOM element
        const el = document.createElement('div');
        el.className = 'virtual-scroll-item';
        el.style.height = `${this.options.itemHeight}px`;
        el.dataset.index = index;

        // Render item content using existing renderRaceCards logic
        this.renderItemContent(item, el);

        // Cache the element
        this.renderedItems.set(key, el);

        // Append to container
        this.scrollContainer.appendChild(el);
    }

    /**
     * Render the content of a single race card
     */
    renderItemContent(item, container) {
        const data = item.data;
        
        // Create header
        const header = document.createElement('div');
        header.className = 'race-block-header';
        header.innerHTML = `
            <span class="race-block-title">${data.track} — Race ${data.race_number}</span>
            <span class="race-block-meta">${data.race_name || ''}</span>
            <span class="race-timer" data-time="${data.race_time}">--:--</span>
        `;

        // Create table wrapper
        const tableWrapper = document.createElement('div');
        tableWrapper.className = 'table-wrapper';
        
        // Create table header
        const thead = document.createElement('thead');
        thead.innerHTML = `
            <tr>
                <th>#</th><th>Horse</th><th>Bar</th><th class="col-jockey">Jockey</th>
                <th>Form</th><th class="col-career">Career W%</th><th>Track W%</th>
                <th class="col-dist">Dist W%</th><th>Fair Value %</th><th>Fair Odds</th>
                <th class="col-tote">Tote</th><th class="col-overlay">Overlay</th><th>Rating</th>
            </tr>
        `;

        // Create table body with visible rows only
        const tbody = document.createElement('tbody');
        
        // Get filtered runners based on current filters
        const ratingFilter = document.getElementById('filter-rating').value;
        let runners = data.runners || [];
        
        if (ratingFilter !== 'ALL') {
            runners = runners.filter(r => r.rating === ratingFilter);
        }

        // Limit rows for performance (show top 10)
        const maxRows = Math.min(runners.length, 10);
        
        for (let j = 0; j < maxRows; j++) {
            const runner = runners[j];
            if (!runner) continue;

            const row = document.createElement('tr');
            row.className = `rank-${j + 1}`;
            
            // Calculate rank styling
            let winStyle = '';
            const result = this.getResult(data.track, data.race_number);
            if (result && result.winner) {
                const winnerLower = result.winner.toLowerCase();
                const horseName = runner.horse_name?.toLowerCase() || '';
                if (winnerLower === horseName) {
                    winStyle = 'style="background:#1a2010;border-left:3px solid #2a9d8f"';
                }
            }

            row.innerHTML = `
                <td><span class="rank-badge rank-${j + 1}">${j + 1}</span></td>
                <td><strong>${runner.horse_name || 'Unknown'}</strong>${winStyle ? ' ✅' : ''}</td>
                <td>${runner.barrier !== null && runner.barrier !== undefined ? runner.barrier : '--'}</td>
                <td class="col-jockey">${runner.jockey || '--'}</td>
                <td><span class="form-string">${this.formatForm(runner.form_string || '')}</span></td>
                <td class="col-career ${this.statClass(runner.career_wins)}">${runner.career_wins || '--'}</td>
                <td class="${this.statClass(runner.track_wins)}">${runner.track_wins || '--'}</td>
                <td class="col-dist ${this.statClass(runner.dist_wins)}">${runner.dist_wins || '--'}</td>
                <td><strong>${runner.fair_value != null ? runner.fair_value.toFixed(1) + '%' : '--'}</strong></td>
                <td class="fair-odds">${runner.est_fair_odds != null ? '$' + runner.est_fair_odds.toFixed(2) : '--'}</td>
                <td class="col-tote">${runner.tote_odds > 0 ? '$' + runner.tote_odds.toFixed(2) : '--'}</td>
                <td class="col-overlay ${((runner.overlay_score || 0) > 0 ? 'score-positive' : 'score-negative')}">
                    ${runner.overlay_score != null && runner.tote_odds > 0 ? runner.overlay_score.toFixed(2) : '--'}
                </td>
                <td><span class="badge ${(runner.rating||'NONE').replace('/','')}">${runner.rating || 'NONE'}</span></td>
            `;

            tbody.appendChild(row);
        }

        // Add result footer if needed
        const raceKey = `${data.track}_${data.race_number}`;
        const resulted = this.isResulted(data.race_time);
        
        if (resulted) {
            const footerId = `result-footer-${raceKey}`;
            const existingFooter = document.getElementById(footerId);
            
            if (!existingFooter) {
                const result = this.getResult(data.track, data.race_number);
                
                let footerHTML = '';
                if (result) {
                    footerHTML = `
                        <div class="result-display">
                            <span class="result-label">Result</span>
                            <span class="result-winner">🥇 ${result.winner}</span>
                            ${result.second ? `<span style="color:#c0c0c0">🥈 ${result.second}</span>` : ''}
                            ${result.third ? `<span style="color:#cd7f32">🥉 ${result.third}</span>` : ''}
                            <button class="result-enter-btn" onclick="showResultInput('${data.track}', ${data.race_number})">Edit</button>
                        </div>
                    `;
                } else {
                    footerHTML = `
                        <div class="result-display">
                            <span class="result-label">Result</span>
                            <span style="color:#555">Not entered yet</span>
                            <button class="result-enter-btn" onclick="showResultInput('${data.track}', ${data.race_number})">+ Enter Result</button>
                        </div>
                    `;
                }

                const footer = document.createElement('div');
                footer.id = footerId;
                footer.innerHTML = footerHTML;
                
                tableWrapper.appendChild(footer);
            }
        } else {
            // Add edit buttons for non-resulted races
            runners.forEach((runner, j) => {
                const row = tbody.children[j];
                if (row) {
                    const lastCell = row.lastElementChild;
                    const editBtn = document.createElement('button');
                    editBtn.className = 'result-enter-btn';
                    editBtn.textContent = '+ Enter Result';
                    editBtn.style.cssText = `
                        margin: 4px;
                        padding: 4px 8px;
                        background: #3b82f6;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 12px;
                    `;
                    editBtn.onclick = () => showResultInput(data.track, data.race_number);
                    
                    const btnContainer = document.createElement('div');
                    btnContainer.style.cssText = 'display:flex; gap:4px; margin-top:8px;';
                    btnContainer.appendChild(editBtn);
                    
                    row.appendChild(btnContainer);
                }
            });
        }

        tableWrapper.appendChild(thead);
        tableWrapper.appendChild(tbody);
        
        container.appendChild(header);
        container.appendChild(tableWrapper);
    }

    /**
     * Render all visible items at once (fallback)
     */
    render() {
        // Clear existing rendered items
        this.renderedItems.clear();
        
        const scrollTop = this.scrollContainer.scrollTop;
        const viewportHeight = this.scrollContainer.clientHeight;
        
        // Calculate visible range with buffer
        const startOffset = Math.max(0, Math.floor(scrollTop / this.options.itemHeight));
        const endOffset = Math.min(
            this.items.length - 1,
            Math.ceil((scrollTop + viewportHeight) / this.options.itemHeight)
        );

        // Render items in visible range plus buffer
        for (let i = startOffset; i <= endOffset; i++) {
            if (i >= this.items.length || i < 0) continue;
            
            const itemIndex = Math.min(i, this.items.length - 1);
            this.renderItem(this.items[itemIndex], itemIndex);
        }

        // Ensure minimum items are always rendered
        while (this.scrollContainer.children.length < this.options.minItems) {
            if (this.visibleEnd >= this.items.length - 1) break;
            const nextIndex = Math.min(this.visibleEnd + 1, this.items.length - 1);
            this.renderItem(this.items[nextIndex], nextIndex);
        }

        // Ensure maximum items cap is respected
        while (this.scrollContainer.children.length > this.options.maxItems) {
            if (this.scrollContainer.lastChild) {
                this.scrollContainer.removeChild(this.scrollContainer.lastChild);
            }
        }
    }

    /**
     * Helper: Format form string with colored spans
     */
    formatForm(form) {
        if (!form || form.length === 0) return '';
        
        let out = '';
        for (let i = 0; i < form.length; i++) {
            const ch = form[i];
            if (ch === '1') out += '<span class="form-win">' + ch + '</span>';
            else if (ch === '2' || ch === '3') out += '<span class="form-place">' + ch + '</span>';
            else if (ch >= '4' && ch <= '9') out += '<span class="form-miss">' + ch + '</span>';
            else out += ch;
        }
        return out;
    }

    /**
     * Helper: Determine styling class for stats
     */
    statClass(val) {
        if (!val) return '';
        const n = parseFloat(val);
        if (n >= 30) return 'stat-high';
        if (n >= 15) return 'stat-mid';
        return 'stat-low';
    }

    /**
     * Helper: Get result for a race
     */
    getResult(track, raceNumber) {
        const key = `${track}_${raceNumber}`;
        return this.raceResults?.[key] || null;
    }

    /**
     * Helper: Check if race is resulted
     */
    isResulted(timeStr) {
        if (!timeStr) return false;
        
        const now = new Date();
        const parts = timeStr.split(':');
        const h = parseInt(parts[0]);
        const m = parseInt(parts[1]);
        const raceTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);
        
        return raceTime < now && (raceTime - now) / 1000 < -2700; // More than 45 mins ago
    }

    /**
     * Cleanup on unmount
     */
    destroy() {
        if (this.observer) {
            this.observer.disconnect();
        }
        
        // Remove scroll listener
        this.scrollContainer.removeEventListener('scroll', () => {});
        
        // Clear cached elements
        this.renderedItems.clear();
        
        // Remove from DOM
        if (this.container && this.scrollContainer.parentNode) {
            this.container.removeChild(this.scrollContainer);
        }
    }
}

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.VirtualScroll = VirtualScroll;
}
