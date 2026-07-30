from fastapi import FastAPI
from stock_tool import build_report

app = FastAPI(
    title="a_Quant",
    description="A composite stock signal analyzer — trend, risk, volume, institutional & insider activity, and fundamentals, all in one report.",
    version="1.0.0",
)


@app.get("/report/{ticker}")
def report(ticker: str):
    """API endpoint: returns the full signal report for a given ticker as JSON."""
    return build_report(ticker.upper())