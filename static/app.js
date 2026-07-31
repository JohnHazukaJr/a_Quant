// GitHub Pages only hosts the static frontend, so it must call the backend
// on its own hosted domain instead of a same-origin relative path.
const API_BASE = window.location.hostname === "johnhazukajr.github.io"
    ? "https://a-quant.onrender.com"
    : "";

// Elements looked up once and reused — the script runs after these exist
// in the DOM (script tags sit at the end of <body>), and none of them are
// ever replaced, so there's no need to re-query on every call.
const tickerInputEl = document.getElementById("tickerInput");
const suggestionsDropdownEl = document.getElementById("tickerSuggestions");
const suggestionsHintEl = document.getElementById("suggestionsHint");
const reportButtonEl = document.querySelector(".search-bar button");
const resultsEl = document.getElementById("results");

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

let currentAbortController = null;

function renderMessage(text, cls) {
    resultsEl.innerHTML = `<p class="${cls}">${text}</p>`;
}

let searchAbortController = null;
let currentSuggestions = [];
let currentSuggestionEls = [];
let activeSuggestionIndex = -1;

const SEARCH_DEBOUNCE_MS = 250;
const MIN_SUGGESTION_QUERY_LENGTH = 2;

function debounce(fn, delay) {
    let timer = null;
    const debounced = (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
    debounced.cancel = () => clearTimeout(timer);
    return debounced;
}

function closeSuggestions() {
    suggestionsDropdownEl.hidden = true;
    suggestionsDropdownEl.innerHTML = "";
    suggestionsHintEl.hidden = true;
    currentSuggestions = [];
    currentSuggestionEls = [];
    activeSuggestionIndex = -1;
    tickerInputEl.setAttribute("aria-expanded", "false");
    tickerInputEl.removeAttribute("aria-activedescendant");
}

function showUnavailableHint() {
    closeSuggestions();
    suggestionsHintEl.hidden = false;
}

function moveActiveSuggestion(delta) {
    const count = currentSuggestions.length;
    activeSuggestionIndex = (activeSuggestionIndex + delta + count) % count;
    updateActiveSuggestion();
}

function updateActiveSuggestion() {
    currentSuggestionEls.forEach((item, i) => item.classList.toggle("active", i === activeSuggestionIndex));

    if (activeSuggestionIndex >= 0) {
        tickerInputEl.setAttribute("aria-activedescendant", `suggestion-${activeSuggestionIndex}`);
    } else {
        tickerInputEl.removeAttribute("aria-activedescendant");
    }
}

function renderSuggestions(results) {
    currentSuggestions = results;
    activeSuggestionIndex = -1;
    suggestionsHintEl.hidden = true;

    if (results.length === 0) {
        closeSuggestions();
        return;
    }

    suggestionsDropdownEl.innerHTML = results.map((r, i) => `
        <li class="suggestion-item" role="option" id="suggestion-${i}">
            <span class="suggestion-symbol">${r.symbol}</span>
            <span class="suggestion-meta">${r.name}${r.exchange ? " — " + r.exchange : ""}</span>
        </li>
    `).join("");
    currentSuggestionEls = Array.from(suggestionsDropdownEl.children);
    suggestionsDropdownEl.hidden = false;
    tickerInputEl.setAttribute("aria-expanded", "true");
}

function selectSuggestion(index) {
    const item = currentSuggestions[index];
    if (!item) return;
    tickerInputEl.value = item.symbol;
    closeSuggestions();
    getReport();
}

async function fetchSuggestions(query) {
    if (searchAbortController) searchAbortController.abort();
    const controller = new AbortController();
    searchAbortController = controller;

    try {
        const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        const data = await response.json();
        // A report submission may have started while this was in flight —
        // don't pop the dropdown open over the results that are now loading.
        if (reportButtonEl.disabled) return;
        if (!response.ok || !data.ok) {
            showUnavailableHint();
            return;
        }
        renderSuggestions(data.results);
    } catch (err) {
        if (err.name === "AbortError") return;
        if (reportButtonEl.disabled) return;
        showUnavailableHint();
    }
}

const debouncedFetchSuggestions = debounce(fetchSuggestions, SEARCH_DEBOUNCE_MS);

async function getReport() {
    const ticker = tickerInputEl.value.trim().toUpperCase();

    if (!ticker) {
        renderMessage("Enter a ticker first.", "status-message");
        return;
    }

    // A report submission supersedes any pending/in-flight autocomplete
    // work — cancel it and close the dropdown before it can pop back open
    // over the results this call is about to render.
    debouncedFetchSuggestions.cancel();
    if (searchAbortController) searchAbortController.abort();
    closeSuggestions();

    if (currentAbortController) currentAbortController.abort();
    const controller = new AbortController();
    currentAbortController = controller;

    reportButtonEl.disabled = true;
    const originalButtonText = reportButtonEl.textContent;
    reportButtonEl.textContent = "Loading…";
    renderMessage("Loading report…", "status-message");

    let data;
    try {
        const response = await fetch(`${API_BASE}/report/${encodeURIComponent(ticker)}`, { signal: controller.signal });
        data = await response.json();
        if (!response.ok) {
            renderMessage(data.error || "Something went wrong. Please try again.", "status-message error-message");
            return;
        }
    } catch (err) {
        if (err.name === "AbortError") return;
        renderMessage("Network error — check your connection and try again.", "status-message error-message");
        return;
    } finally {
        reportButtonEl.disabled = false;
        reportButtonEl.textContent = originalButtonText;
    }

    const liveClass = trendClass(data.day_change_note);
    const trendClassName = trendClass(data.trend);
    const riskClass = LEVEL_COLORS[data.risk.category];
    const volClass = LEVEL_COLORS[data.volume.level];
    const instClass = LEVEL_COLORS[data.institutional.level];
    const insiderClass = LEVEL_COLORS[data.insider.level];
    const fcfCls = fcfClass(data.fcf);

    resultsEl.innerHTML = `
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

document.addEventListener("DOMContentLoaded", () => {
    tickerInputEl.addEventListener("input", () => {
        const query = tickerInputEl.value.trim();
        if (query.length < MIN_SUGGESTION_QUERY_LENGTH) {
            closeSuggestions();
            return;
        }
        debouncedFetchSuggestions(query);
    });

    tickerInputEl.addEventListener("keydown", (e) => {
        const hasSuggestions = currentSuggestions.length > 0 && !suggestionsDropdownEl.hidden;

        if (hasSuggestions && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            e.preventDefault();
            moveActiveSuggestion(e.key === "ArrowDown" ? 1 : -1);
            return;
        }
        if (hasSuggestions && e.key === "Escape") {
            closeSuggestions();
            return;
        }
        if (e.key === "Enter") {
            if (hasSuggestions && activeSuggestionIndex >= 0) {
                e.preventDefault();
                selectSuggestion(activeSuggestionIndex);
                return;
            }
            getReport();
        }
    });

    suggestionsDropdownEl.addEventListener("click", (e) => {
        const item = e.target.closest(".suggestion-item");
        if (!item) return;
        selectSuggestion(currentSuggestionEls.indexOf(item));
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".ticker-input-wrap")) closeSuggestions();
    });
});
