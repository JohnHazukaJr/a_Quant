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


# --- Try it out ---
data = get_price_history("AAPL")
prices = data["Close"].tolist()
print(data.columns)
print(len(prices))

result = analyze_stock("AAPL", prices)
print(result)
print(result["ticker"])
print(result["average_daily_return"])

explanation = explain_summary(result)
print(explanation)

daily_returns = calculate_returns(prices)
ann_vol = annualized_volatility(daily_returns)
scale = volatility_scale(ann_vol)
print(f"Annualized volatility: {ann_vol}%")
print(scale)

def get_volume_history(ticker, period="3mo"):
    """Pull real historical daily trading volume for a ticker."""
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    return history["Volume"].tolist()


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


# Try it out
volumes = get_volume_history("AAPL")
rel_vol = relative_volume(volumes)
vol_signal = volume_signal(rel_vol)
print(f"Relative volume: {rel_vol}x")
print(vol_signal)