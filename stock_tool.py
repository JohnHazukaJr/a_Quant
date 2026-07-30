import statistics
import math
import yfinance as yf


def get_price_history(ticker, period="3mo"):
    """Pull real historical daily price and volume data for a ticker."""
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    return history


def percent_return(start_price, end_price):
    """Calculate the percentage return from start_price to end_price."""
    change = end_price - start_price
    return round((change / start_price) * 100, 2)


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


def generate_report(ticker):
    """Build the full composite signal report for a given ticker."""
    price_data = get_price_history(ticker)
    prices = price_data["Close"].tolist()
    volumes = price_data["Volume"].tolist()

    summary = analyze_stock(ticker, prices)
    trend_text = explain_summary(summary)

    daily_returns = calculate_returns(prices)
    ann_vol = annualized_volatility(daily_returns)
    risk = volatility_scale(ann_vol)

    rel_vol = relative_volume(volumes)
    vol = volume_signal(rel_vol)

    holders = get_institutional_summary(ticker)
    inst = institutional_signal(holders)

    insiders = get_insider_activity(ticker)
    insider = insider_signal(insiders)

    print(f"\n=== Stock Signal Report: {ticker} ===")
    print(f"Trend:                    {trend_text}")
    print(f"Risk:                     {risk['category']} — {risk['note']}")
    print(f"Volume:                   {vol['level']} ({rel_vol}x normal) — {vol['note']}")
    print(f"Institutional (quarterly): {inst['level']} — {inst['note']}")
    print(f"Insider activity (recent): {insider['level']} — {insider['note']}")
    print("\nNote: this is an educational analysis tool, not financial advice.")
    print("No combination of these signals reliably predicts future price movement.")


# --- Try it out ---
generate_report("AAPL")