from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from stock_tool import InvalidTickerError, TickerDataError

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_report_success():
    canned = {"ticker": "AAPL", "trend": "up"}
    with patch("api.build_report", return_value=canned):
        response = client.get("/report/AAPL")
    assert response.status_code == 200
    assert response.json() == canned


def test_report_invalid_ticker_returns_400():
    with patch("api.build_report", side_effect=InvalidTickerError("bad ticker")):
        response = client.get("/report/notaticker")
    assert response.status_code == 400
    assert response.json() == {"error": "bad ticker"}


def test_report_no_data_returns_404():
    with patch("api.build_report", side_effect=TickerDataError("no data")):
        response = client.get("/report/ZZZZ9")
    assert response.status_code == 404
    assert response.json() == {"error": "no data"}


def test_report_unexpected_error_returns_502():
    with patch("api.build_report", side_effect=RuntimeError("boom")):
        response = client.get("/report/AAPL")
    assert response.status_code == 502
    assert response.json() == {"error": "boom"}
