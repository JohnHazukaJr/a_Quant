// GitHub Pages only hosts the static frontend, so it must call the backend
// on its own hosted domain instead of a same-origin relative path.
const API_BASE = window.location.hostname === "johnhazukajr.github.io"
    ? "https://a-quant.onrender.com"
    : "";

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

const DIRECTION_ICONS = {
    "bubble-positive": "trending-up",
    "bubble-warning": "trending-down",
    "bubble-neutral": "minus",
};

function trendClass(trendText) {
    if (trendText.includes("up")) return "bubble-positive";
    if (trendText.includes("down")) return "bubble-warning";
    return "bubble-neutral";
}

function fcfClass(fcf) {
    if (fcf.per_share === null) return "bubble-neutral";
    return fcf.per_share > 0 ? "bubble-positive" : "bubble-warning";
}

function bubble(cls, icon) {
    return `<div class="bubble ${cls}"><i data-lucide="${icon}"></i></div>`;
}

async function getReport() {
    const ticker = document.getElementById("tickerInput").value;
    const response = await fetch(`${API_BASE}/report/${ticker}`);
    const data = await response.json();

    const liveClass = trendClass(data.day_change_note);
    const trendClassName = trendClass(data.trend);
    const riskClass = LEVEL_COLORS[data.risk.category];
    const volClass = LEVEL_COLORS[data.volume.level];
    const instClass = LEVEL_COLORS[data.institutional.level];
    const insiderClass = LEVEL_COLORS[data.insider.level];
    const fcfCls = fcfClass(data.fcf);

    document.getElementById("results").innerHTML = `
        <div class="card">
            ${bubble(liveClass, DIRECTION_ICONS[liveClass])}
            <div>
                <div class="card-label">${data.ticker} — Live</div>
                <div class="card-value">$${data.live_quote.last_price} — ${data.day_change_note}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(trendClassName, DIRECTION_ICONS[trendClassName])}
            <div>
                <div class="card-label">Trend</div>
                <div class="card-value">${data.trend}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(riskClass, "shield")}
            <div>
                <div class="card-label">Risk</div>
                <div class="card-value">${data.risk.category} — ${data.risk.note}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(volClass, "bar-chart-3")}
            <div>
                <div class="card-label">Volume</div>
                <div class="card-value">${data.volume.level} (${data.volume.ratio}x normal) — ${data.volume.note}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(instClass, "building-2")}
            <div>
                <div class="card-label">Institutional</div>
                <div class="card-value">${data.institutional.level} — ${data.institutional.note}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(insiderClass, "user")}
            <div>
                <div class="card-label">Insider Activity</div>
                <div class="card-value">${data.insider.level} — ${data.insider.note}</div>
            </div>
        </div>
        <div class="card">
            ${bubble(fcfCls, "banknote")}
            <div>
                <div class="card-label">Free Cash Flow / Share</div>
                <div class="card-value">${data.fcf.per_share !== null ? '$' + data.fcf.per_share : 'N/A'} — ${data.fcf.note}</div>
            </div>
        </div>
    `;

    lucide.createIcons();
}
