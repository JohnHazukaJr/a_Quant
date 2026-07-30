async function getReport() {
        const ticker = document.getElementById("tickerInput").ariaValueMax;
        const response = await fetch('/report/${ticker}');
        const data = await response.json();

         document.getElementById("results").innerHTML = `
        <h2>${data.ticker}</h2>
        <p>Price: $${data.live_quote.last_price} (${data.day_change_note})</p>
        <p>Trend: ${data.trend}</p>
        <p>Risk: ${data.risk.category} — ${data.risk.note}</p>
    `;
}