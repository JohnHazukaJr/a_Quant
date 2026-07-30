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

let currentAbortController = null;

function renderMessage(text, cls) {
    document.getElementById("results").innerHTML = `<p class="${cls}">${text}</p>`;
}

let searchAbortController = null;
let currentSuggestions = [];
let activeSuggestionIndex = -1;

const SEARCH_DEBOUNCE_MS = 250;
const MIN_SUGGESTION_QUERY_LENGTH = 2;

function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function closeSuggestions() {
    const dropdown = document.getElementById("tickerSuggestions");
    const hint = document.getElementById("suggestionsHint");
    const input = document.getElementById("tickerInput");

    dropdown.hidden = true;
    dropdown.innerHTML = "";
    hint.hidden = true;
    currentSuggestions = [];
    activeSuggestionIndex = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
}

function showUnavailableHint() {
    const dropdown = document.getElementById("tickerSuggestions");
    const hint = document.getElementById("suggestionsHint");
    const input = document.getElementById("tickerInput");

    dropdown.hidden = true;
    dropdown.innerHTML = "";
    currentSuggestions = [];
    activeSuggestionIndex = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    hint.hidden = false;
}

function updateActiveSuggestion() {
    const input = document.getElementById("tickerInput");
    const items = document.querySelectorAll("#tickerSuggestions .suggestion-item");
    items.forEach((item, i) => item.classList.toggle("active", i === activeSuggestionIndex));

    if (activeSuggestionIndex >= 0) {
        input.setAttribute("aria-activedescendant", `suggestion-${activeSuggestionIndex}`);
    } else {
        input.removeAttribute("aria-activedescendant");
    }
}

function renderSuggestions(results) {
    currentSuggestions = results;
    activeSuggestionIndex = -1;

    const dropdown = document.getElementById("tickerSuggestions");
    const hint = document.getElementById("suggestionsHint");
    const input = document.getElementById("tickerInput");
    hint.hidden = true;

    if (results.length === 0) {
        closeSuggestions();
        return;
    }

    dropdown.innerHTML = results.map((r, i) => `
        <li class="suggestion-item" role="option" id="suggestion-${i}">
            <span class="suggestion-symbol">${r.symbol}</span>
            <span class="suggestion-meta">${r.name}${r.exchange ? " — " + r.exchange : ""}</span>
        </li>
    `).join("");
    dropdown.hidden = false;
    input.setAttribute("aria-expanded", "true");
}

function selectSuggestion(index) {
    const item = currentSuggestions[index];
    if (!item) return;
    document.getElementById("tickerInput").value = item.symbol;
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
        if (!response.ok || !data.ok) {
            showUnavailableHint();
            return;
        }
        renderSuggestions(data.results);
    } catch (err) {
        if (err.name === "AbortError") return;
        showUnavailableHint();
    }
}

const debouncedFetchSuggestions = debounce(fetchSuggestions, SEARCH_DEBOUNCE_MS);

async function getReport() {
    const input = document.getElementById("tickerInput");
    const button = document.querySelector(".search-bar button");
    const ticker = input.value.trim().toUpperCase();

    if (!ticker) {
        renderMessage("Enter a ticker first.", "status-message");
        return;
    }

    if (currentAbortController) currentAbortController.abort();
    const controller = new AbortController();
    currentAbortController = controller;

    button.disabled = true;
    const originalButtonText = button.textContent;
    button.textContent = "Loading…";
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
        button.disabled = false;
        button.textContent = originalButtonText;
    }

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

document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("tickerInput");
    const dropdown = document.getElementById("tickerSuggestions");

    input.addEventListener("input", () => {
        const query = input.value.trim();
        if (query.length < MIN_SUGGESTION_QUERY_LENGTH) {
            closeSuggestions();
            return;
        }
        debouncedFetchSuggestions(query);
    });

    input.addEventListener("keydown", (e) => {
        const hasSuggestions = currentSuggestions.length > 0 && !dropdown.hidden;

        if (hasSuggestions && e.key === "ArrowDown") {
            e.preventDefault();
            activeSuggestionIndex = (activeSuggestionIndex + 1) % currentSuggestions.length;
            updateActiveSuggestion();
            return;
        }
        if (hasSuggestions && e.key === "ArrowUp") {
            e.preventDefault();
            activeSuggestionIndex = (activeSuggestionIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
            updateActiveSuggestion();
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

    dropdown.addEventListener("click", (e) => {
        const item = e.target.closest(".suggestion-item");
        if (!item) return;
        const index = Array.from(dropdown.children).indexOf(item);
        selectSuggestion(index);
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".ticker-input-wrap")) closeSuggestions();
    });
});
