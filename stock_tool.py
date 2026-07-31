import functools
import re
import statistics
import math
import threading
import time
import yfinance as yf
from yfinance.exceptions import YFRateLimitError


class StockToolError(Exception):
    """Base class for expected, user-facing errors from stock_tool."""


class InvalidTickerError(StockToolError):
    """Ticker string failed basic format validation before any network call."""


class TickerDataError(StockToolError):
    """Ticker is well-formed but yfinance returned no usable data for it."""


class RateLimitedError(StockToolError):
    """Yahoo Finance is rate-limiting this server right now."""


_rate_limit_lock = threading.Lock()
_rate_limited_until = 0.0
RATE_LIMIT_COOLDOWN_SECONDS = 30


def _note_rate_limited():
    """Record that Yahoo just rate-limited us. The limit is effectively
    IP-wide (not per-ticker), so once it happens, every other in-flight or
    new lookup is about to hit it too — no point letting each one waste
    its own retry budget finding that out independently."""
    global _rate_limited_until
    with _rate_limit_lock:
        _rate_limited_until = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS


def _check_rate_limit_cooldown():
    """Raise immediately, without touching the network, if we're still
    within a cooldown window from a recent rate-limit hit."""
    with _rate_limit_lock:
        remaining = _rate_limited_until - time.monotonic()
    if remaining > 0:
        raise RateLimitedError(
            f"Yahoo Finance is rate-limiting this server right now — try again in about {int(remaining) + 1}s."
        )


def _ticker_char_pattern(max_length):
    return re.compile(r"^[A-Z0-9.\-]{1,%d}$" % max_length)


def _normalize_ticker_input(value):
    """Strip/uppercase raw ticker input, shared by full-ticker validation
    and partial-prefix search normalization."""
    return (value or "").strip().upper()


TICKER_RE = _ticker_char_pattern(10)


def validate_ticker(ticker):
    """Normalize and validate a ticker symbol before any network call."""
    ticker = _normalize_ticker_input(ticker)
    if not TICKER_RE.match(ticker):
        raise InvalidTickerError(f"'{ticker}' doesn't look like a valid ticker symbol.")
    return ticker


def retry_on_failure(max_attempts=3, base_delay=0.5):
    """Retry a flaky network call with exponential backoff. Yahoo Finance
    occasionally has brief transient failures that clear up within a
    couple of seconds, which this papers over.

    A rate limit is different: it's Yahoo explicitly telling us to back
    off, and retrying within ~1.5s of backoff just spends the retry
    budget confirming we're still rate-limited. So that one exception
    type is deliberately NOT retried here — it's noted (see
    _note_rate_limited) and re-raised immediately."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except YFRateLimitError:
                    _note_rate_limited()
                    raise
                except Exception:
                    if attempt == max_attempts:
                        raise
                    time.sleep(base_delay * (2 ** (attempt - 1)))
        return wrapper
    return decorator


@retry_on_failure()
def get_price_history(ticker, period="3mo"):
    """Pull real historical daily price and volume data for a ticker."""
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    return history


@retry_on_failure()
def get_live_quote(ticker):
    """Pull the current real-time-delayed quote for a ticker (price, day
    range, market cap) — the freshest data yfinance can provide."""
    stock = yf.Ticker(ticker)
    quote = stock.fast_info
    return {
        "last_price": round(quote["lastPrice"], 2),
        "previous_close": round(quote["previousClose"], 2),
        "day_high": round(quote["dayHigh"], 2),
        "day_low": round(quote["dayLow"], 2),
        "market_cap": quote["marketCap"],
    }


def percent_return(start_price, end_price):
    """Calculate the percentage return from start_price to end_price."""
    change = end_price - start_price
    return round((change / start_price) * 100, 2)


def live_quote_summary(quote):
    """Turn a live quote dict into a plain-English day-change summary."""
    day_change = percent_return(quote["previous_close"], quote["last_price"])

    if day_change > 0:
        note = f"up {day_change}% on the day"
    elif day_change < 0:
        note = f"down {abs(day_change)}% on the day"
    else:
        note = "unchanged on the day"

    return {"day_change": day_change, "note": note}


def calculate_returns(price_list):
    """Given a list of prices, return a list of daily percent returns."""
    returns = []
    for i in range(len(price_list) - 1):
        today = price_list[i]
        tomorrow = price_list[i + 1]
        ret = percent_return(today, tomorrow)
        returns.append(ret)
    return returns


def average_return(returns_list):
    """Given a list of returns, calculate the average return."""
    return sum(returns_list) / len(returns_list)


def analyze_stock(ticker, prices):
    """Build a summary dictionary of stats for one stock"""
    daily_returns = calculate_returns(prices)
    avg = average_return(daily_returns)

    summary = {
        "ticker": ticker,
        "latest_price": prices[-1],
        "average_daily_return": round(avg, 2),
        "num_days": len(prices),
    }
    return summary


def explain_summary(summary):
    """Turn a stock summary dictionary into a plain-English explanation"""
    ticker = summary["ticker"]
    avg = summary["average_daily_return"]

    if avg > 0:
        trend = f"{ticker} has been trending upwards on average ({avg}% per day)."
    elif avg < 0:
        trend = f"{ticker} has been trending downwards on average ({avg}% per day)."
    else:
        trend = f"{ticker} has been flat on average."

    return trend


def annualized_volatility(daily_returns):
    """Convert daily volatility into the standard annualized form used in finance."""
    daily_vol = statistics.stdev(daily_returns)
    return round(daily_vol * math.sqrt(252), 2)


def volatility_scale(annual_vol):
    """Map annualized volatility (%) to a beginner-friendly risk category."""
    if annual_vol < 20:
        category = "Low"
        note = "Prices have been fairly steady over the year."
    elif annual_vol < 40:
        category = "Moderate"
        note = "Prices swing a normal, moderate amount over the year."
    else:
        category = "High"
        note = "Prices swing a lot over the year — expect a bumpier ride."

    return {"category": category, "note": note}


def relative_volume(volumes):
    """Compare the most recent day's volume to its own historical average."""
    latest = volumes[-1]
    historical_avg = sum(volumes[:-1]) / len(volumes[:-1])
    return round(latest / historical_avg, 2)


def volume_signal(rel_vol):
    """Map a relative volume ratio to a beginner-friendly interpretation."""
    if rel_vol >= 1.5:
        return {"level": "High", "note": "Trading activity is well above normal — possible institutional interest."}
    elif rel_vol <= 0.5:
        return {"level": "Low", "note": "Trading activity is well below normal — quieter than usual."}
    else:
        return {"level": "Normal", "note": "Trading activity is within its typical range."}


@retry_on_failure()
def get_institutional_summary(ticker):
    """Pull real institutional ownership data for a ticker."""
    stock = yf.Ticker(ticker)
    holders = stock.institutional_holders
    return holders


def institutional_signal(holders_df):
    """Summarize whether institutions have broadly been increasing or
    decreasing their stakes. Note: exact pctChange values from this data
    source are sometimes unreliable, so we only trust the direction
    (up/down/flat), not the precise magnitude."""
    changes = holders_df["pctChange"].tolist()

    increased = 0
    decreased = 0
    for c in changes:
        if c > 0:
            increased += 1
        elif c < 0:
            decreased += 1

    total = len(changes)

    if increased > decreased:
        level = "Accumulating"
        note = f"{increased} of {total} major institutional holders increased their position last quarter."
    elif decreased > increased:
        level = "Reducing"
        note = f"{decreased} of {total} major institutional holders decreased their position last quarter."
    else:
        level = "Mixed"
        note = "Institutional holders were evenly split between buying and selling last quarter."

    return {"level": level, "note": note}


@retry_on_failure()
def get_insider_activity(ticker):
    """Pull recent insider (executive/board) transaction data — much
    more current than quarterly institutional filings (insiders must
    report trades within 2 business days)."""
    stock = yf.Ticker(ticker)
    transactions = stock.insider_transactions
    return transactions


def insider_signal(insider_df):
    """Classify insider transactions using the free-text 'Text' field
    (the structured 'Transaction' field is unreliable for this data
    source). Gifts and blank entries are excluded, since they aren't
    real buy/sell market signals."""
    texts = insider_df["Text"].tolist()

    buys = 0
    sells = 0
    for text in texts:
        text = text.lower()
        if "sale" in text:
            sells += 1
        elif "purchase" in text or "buy" in text:
            buys += 1
        # gifts, blanks, and anything else are intentionally skipped

    if buys > sells:
        level = "Buying"
        note = f"{buys} insider purchases vs. {sells} sales in recent filings — purchases are the rarer, more bullish signal."
    elif sells > buys:
        level = "Selling"
        note = f"{sells} insider sales vs. {buys} purchases — note that routine insider selling (taxes, diversification) is common and not necessarily bearish."
    else:
        level = "Mixed"
        note = f"Insider activity was roughly balanced ({buys} buys, {sells} sells)."

    return {"level": level, "note": note}


@retry_on_failure()
def get_fcf_data(ticker):
    """Pull quarterly Free Cash Flow figures and shares outstanding for a
    ticker."""
    stock = yf.Ticker(ticker)
    cashflow = stock.quarterly_cashflow
    if cashflow is None or "Free Cash Flow" not in cashflow.index:
        return None

    return {
        "quarterly_fcf": cashflow.loc["Free Cash Flow"].tolist(),
        "shares": stock.fast_info["shares"],
    }


def fcf_per_share(fcf_data):
    """Sum the trailing four quarters of Free Cash Flow (TTM) and divide
    by shares outstanding."""
    ttm_fcf = sum(fcf_data["quarterly_fcf"][:4])
    per_share = round(ttm_fcf / fcf_data["shares"], 2)

    if per_share > 0:
        note = "Positive — the business generates more cash than it spends, including capex."
    else:
        note = "Negative — the business is burning cash after capital expenditures."

    return {"per_share": per_share, "note": note}


def _cached(cache, lock, ttl_seconds, key, compute):
    """Shared get-or-compute TTL cache: dict + lock + time.monotonic()
    expiry, used for both the report cache and the search cache."""
    now = time.monotonic()
    with lock:
        cached = cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

    value = compute()

    with lock:
        cache[key] = (now + ttl_seconds, value)

    return value


_report_cache = {}  # ticker -> (expires_at, report_dict)
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 60


def _fetch_report_data(ticker):
    """Fetch and assemble the full signal report for a ticker (no caching,
    no validation — always hits the network). Shared by build_report and
    generate_report so there's one source of truth for report assembly."""
    _check_rate_limit_cooldown()

    try:
        quote = get_live_quote(ticker)
    except KeyError:
        raise TickerDataError(f"No data found for '{ticker}' — check the symbol is correct.")
    quote_summary = live_quote_summary(quote)

    price_data = get_price_history(ticker)
    if price_data is None or price_data.empty:
        raise TickerDataError(f"No price data found for '{ticker}' — check the symbol is correct.")

    prices = price_data["Close"].tolist()
    if len(prices) < 2:
        raise TickerDataError(f"Not enough price history for '{ticker}' to compute trend/risk.")

    volumes = price_data["Volume"].tolist()

    summary = analyze_stock(ticker, prices)
    trend_text = explain_summary(summary)

    daily_returns = calculate_returns(prices)
    ann_vol = annualized_volatility(daily_returns)
    risk = volatility_scale(ann_vol)

    rel_vol = relative_volume(volumes)
    vol = volume_signal(rel_vol)

    holders = get_institutional_summary(ticker)
    if holders is not None and not holders.empty:
        inst = institutional_signal(holders)
    else:
        inst = {"level": "N/A", "note": "Not available for this ticker."}

    insiders = get_insider_activity(ticker)
    if insiders is not None and not insiders.empty:
        insider = insider_signal(insiders)
    else:
        insider = {"level": "N/A", "note": "Not available for this ticker."}

    fcf_data = get_fcf_data(ticker)
    if fcf_data is not None and len(fcf_data["quarterly_fcf"]) >= 4:
        fcf = fcf_per_share(fcf_data)
    else:
        fcf = {"per_share": None, "note": "Not available for this ticker."}

    return {
        "ticker": ticker,
        "live_quote": quote,
        "day_change_note": quote_summary["note"],
        "trend": trend_text,
        "risk": risk,
        "volume": {"ratio": rel_vol, **vol},
        "institutional": inst,
        "insider": insider,
        "fcf": fcf,
    }


def build_report(ticker):
    """Validate a ticker, return its cached report if fresh, otherwise
    fetch, cache, and return a full signal report dictionary. This is
    what the API and CLI both use."""
    ticker = validate_ticker(ticker)
    try:
        return _cached(_report_cache, _cache_lock, CACHE_TTL_SECONDS, ticker,
                        lambda: _fetch_report_data(ticker))
    except YFRateLimitError as exc:
        # Normalize the raw yfinance exception to our own type, so callers
        # only ever need to handle one rate-limit exception, regardless of
        # whether this is the request that discovered the limit (this
        # path) or one that arrived during the cooldown that followed
        # (raised directly as RateLimitedError by _check_rate_limit_cooldown).
        raise RateLimitedError(str(exc)) from exc


def generate_report(ticker):
    """Build the full composite signal report for a given ticker and
    print it in plain English."""
    report = build_report(ticker)

    quote = report["live_quote"]
    vol = report["volume"]

    print(f"\n=== Stock Signal Report: {report['ticker']} ===")
    print(f"Live Quote:               ${quote['last_price']} ({report['day_change_note']}), day range ${quote['day_low']}–${quote['day_high']}")
    print(f"Trend:                    {report['trend']}")
    print(f"Risk:                     {report['risk']['category']} — {report['risk']['note']}")
    print(f"Volume:                   {vol['level']} ({vol['ratio']}x normal) — {vol['note']}")
    print(f"Institutional (quarterly): {report['institutional']['level']} — {report['institutional']['note']}")
    print(f"Insider activity (recent): {report['insider']['level']} — {report['insider']['note']}")
    if report["fcf"]["per_share"] is not None:
        print(f"Free Cash Flow/Share (TTM): ${report['fcf']['per_share']}/share — {report['fcf']['note']}")
    else:
        print(f"Free Cash Flow/Share (TTM): {report['fcf']['note']}")
    print("\nNote: this is an educational analysis tool, not financial advice.")
    print("No combination of these signals reliably predicts future price movement.")


PARTIAL_TICKER_RE = _ticker_char_pattern(12)

_search_cache = {}  # (query, max_results) -> (expires_at, results_list)
_search_cache_lock = threading.Lock()
SEARCH_CACHE_TTL_SECONDS = 600  # symbol/name/exchange metadata is far more
                                 # stable than live quotes (60s report cache)


def _normalize_search_query(query):
    """Normalize a partial-ticker search query. Returns None for anything
    that doesn't look like a plausible ticker prefix — unlike
    validate_ticker, this never raises; a bad query just yields no
    suggestions rather than an error."""
    query = _normalize_ticker_input(query)
    if not PARTIAL_TICKER_RE.match(query):
        return None
    return query


@retry_on_failure()
def _lookup_stock(query, max_results):
    """Raw yfinance call, isolated so it's mockable/retryable independently
    of search_tickers' validation/caching/shaping logic."""
    return yf.Lookup(query).get_stock(count=max_results)


def _clean_str(value):
    """yfinance's Lookup data can have missing fields come through as NaN
    (a float, not None) — NaN is truthy in Python, so a plain `x or y`
    fallback lets it slip through, and a raw NaN isn't valid JSON. Only
    pass through real, non-empty strings."""
    return value if isinstance(value, str) and value else ""


def search_tickers(query, max_results=8):
    """Return up to max_results equity ticker suggestions for a partial
    query, as a list of {symbol, name, exchange, quote_type} dicts.

    Returns [] for empty/invalid input or a genuine no-match result — a
    normal, expected state. Returns None if the lookup itself failed after
    retries (e.g. Yahoo is down) — callers use this to distinguish "no
    matches" from "suggestions unavailable right now"."""
    normalized = _normalize_search_query(query)
    if normalized is None:
        return []

    # Not using the shared _cached() helper here: a failed lookup must
    # return None *without* being cached, so a transient Yahoo failure
    # doesn't stick around as "unavailable" for the full TTL — build_report
    # doesn't have this requirement (its failures propagate as exceptions),
    # so the two caches aren't quite interchangeable.
    cache_key = (normalized, max_results)
    now = time.monotonic()
    with _search_cache_lock:
        cached = _search_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    try:
        _check_rate_limit_cooldown()
        df = _lookup_stock(normalized, max_results)
    except Exception:
        return None  # lookup failed (including rate-limited) — distinct from "no matches"

    results = []
    if df is not None and not df.empty:
        results = [
            {
                "symbol": symbol,
                "name": _clean_str(row.get("shortName")) or _clean_str(row.get("longName")),
                "exchange": _clean_str(row.get("exchange")),
                "quote_type": _clean_str(row.get("quoteType")),
            }
            for symbol, row in df.iterrows()
        ]

    with _search_cache_lock:
        _search_cache[cache_key] = (now + SEARCH_CACHE_TTL_SECONDS, results)

    return results


if __name__ == "__main__":
    ticker_input = input("Enter a stock ticker (e.g. AAPL, TSLA, MSFT): ")
    generate_report(ticker_input)
