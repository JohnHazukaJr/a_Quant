from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from stock_tool import build_report

app = FastAPI(
    title="a_Quant",
    description="A composite stock signal analyzer — trend, risk, volume, institutional & insider activity, and fundamentals, all in one report.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://johnhazukajr.github.io"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/report/{ticker}")
def report(ticker: str):
    """API endpoint: returns the full signal report for a given ticker as JSON."""
    return build_report(ticker.upper())


@app.get("/")
def home():
    """Serve the frontend page."""
    return FileResponse("index.html")