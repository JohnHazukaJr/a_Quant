from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from stock_tool import RATE_LIMIT_COOLDOWN_SECONDS, InvalidTickerError, RateLimitedError, TickerDataError

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


def test_report_rate_limited_returns_503_with_retry_after():
    with patch("api.build_report", side_effect=RateLimitedError("slow down")):
        response = client.get("/report/AAPL")
    assert response.status_code == 503
    assert response.json() == {"error": "slow down"}
    assert response.headers["retry-after"] == str(RATE_LIMIT_COOLDOWN_SECONDS)


def test_report_unexpected_error_returns_502():
    with patch("api.build_report", side_effect=RuntimeError("boom")):
        response = client.get("/report/AAPL")
    assert response.status_code == 502
    assert response.json() == {"error": "boom"}


def test_search_success():
    canned = [{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "quote_type": "EQUITY"}]
    with patch("api.search_tickers", return_value=canned):
        response = client.get("/search?q=AAP")
    assert response.status_code == 200
    assert response.json() == {"results": canned, "ok": True}


def test_search_no_query_param():
    with patch("api.search_tickers", return_value=[]) as mock_search:
        response = client.get("/search")
    assert response.status_code == 200
    assert response.json() == {"results": [], "ok": True}
    mock_search.assert_called_once_with("")


def test_search_no_results():
    with patch("api.search_tickers", return_value=[]):
        response = client.get("/search?q=ZZZZ9")
    assert response.status_code == 200
    assert response.json() == {"results": [], "ok": True}


def test_search_lookup_failed_returns_ok_false():
    with patch("api.search_tickers", return_value=None):
        response = client.get("/search?q=AAP")
    assert response.status_code == 200
    assert response.json() == {"results": [], "ok": False}


def test_search_backend_exception_returns_ok_false():
    with patch("api.search_tickers", side_effect=RuntimeError("boom")):
        response = client.get("/search?q=AAP")
    assert response.status_code == 200
    assert response.json() == {"results": [], "ok": False}
