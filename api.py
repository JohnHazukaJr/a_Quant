from fastapi import FastAPI
from stock_tool import build_report

app = FastAPI()

@app.get("report/{ticker}")
def report(ticker: str):
    """API endpoint: returns the full signal report for a given ticker as JSON """
    return build_report(ticker.upper())