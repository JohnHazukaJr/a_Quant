const LEVEL_COLORS = {
    "Low": "bubble-positive",
    "Moderate": "bubble-neutral",
    "High": "bubble-warning",
    "Normal": "bubble-neutral",
    "Accumulating": "bubble-positive",
    "Reducing": "bubble-warning",
    "Mixed": "bubble-neutral",
    "Buying": "bubble-positive",
    "Selling": "bubble-warning",
    "N/A": "bubble-neutral",
};

function trendClass(trendText) {
    if (trendText.includes("upwards")) return "bubble-positive";
    if (trendText.includes("downwards")) return "bubble-warning";
    return "bubble-neutral";
}

function fcfClass(fcf) {
    if (fcf.per_share === null) return "bubble-neutral";
    return fcf.per_share > 0 ? "bubble-positive" : "bubble-warning";
}

async function getReport() {
    const ticker = document.getElementById("tickerInput").value;
    const response = await fetch(`/report/${ticker}`);
    const data = await response.json();

    document.getElementById("results").innerHTML = `
        <div class="card">
            <div class="bubble ${trendClass(data.day_change_note)}"></div>
            <div>
                <div class="card-label">${data.ticker} — Live</div>
                <div class="card-value">$${data.live_quote.last_price} — ${data.day_change_note}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${trendClass(data.trend)}"></div>
            <div>
                <div class="card-label">Trend</div>
                <div class="card-value">${data.trend}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${LEVEL_COLORS[data.risk.category]}"></div>
            <div>
                <div class="card-label">Risk</div>
                <div class="card-value">${data.risk.category} — ${data.risk.note}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${LEVEL_COLORS[data.volume.level]}"></div>
            <div>
                <div class="card-label">Volume</div>
                <div class="card-value">${data.volume.level} (${data.volume.ratio}x normal) — ${data.volume.note}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${LEVEL_COLORS[data.institutional.level]}"></div>
            <div>
                <div class="card-label">Institutional</div>
                <div class="card-value">${data.institutional.level} — ${data.institutional.note}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${LEVEL_COLORS[data.insider.level]}"></div>
            <div>
                <div class="card-label">Insider Activity</div>
                <div class="card-value">${data.insider.level} — ${data.insider.note}</div>
            </div>
        </div>
        <div class="card">
            <div class="bubble ${fcfClass(data.fcf)}"></div>
            <div>
                <div class="card-label">Free Cash Flow / Share</div>
                <div class="card-value">${data.fcf.per_share !== null ? '$' + data.fcf.per_share : 'N/A'} — ${data.fcf.note}</div>
            </div>
        </div>
    `;
}