import logging
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from stock_tool import build_report, InvalidTickerError, TickerDataError

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="a_Quant",
    description="A composite stock signal analyzer — trend, risk, volume, institutional & insider activity, and fundamentals, all in one report.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # keep in sync with API_BASE in static/app.js
    allow_origins=["https://johnhazukajr.github.io"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/report/{ticker}")
def report(ticker: str):
    """API endpoint: returns the full signal report for a given ticker as JSON."""
    try:
        return build_report(ticker)
    except InvalidTickerError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except TickerDataError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except Exception as exc:
        logger.error("build_report(%s) failed:\n%s", ticker, traceback.format_exc())
        return JSONResponse(status_code=502, content={"error": str(exc)})


@app.get("/health")
def health():
    """Cheap liveness check that never touches yfinance."""
    return {"status": "ok"}


@app.get("/")
def home():
    """Serve the frontend page."""
    return FileResponse("index.html")