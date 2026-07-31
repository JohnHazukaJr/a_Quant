from unittest.mock import patch

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

import stock_tool
from stock_tool import (
    InvalidTickerError,
    RateLimitedError,
    TickerDataError,
    analyze_stock,
    annualized_volatility,
    average_return,
    build_report,
    calculate_returns,
    explain_summary,
    fcf_per_share,
    insider_signal,
    institutional_signal,
    percent_return,
    relative_volume,
    validate_ticker,
    volatility_scale,
    volume_signal,
)


def test_percent_return():
    assert percent_return(100, 110) == 10.0
    assert percent_return(100, 90) == -10.0
    assert percent_return(100, 100) == 0.0


def test_calculate_returns():
    assert calculate_returns([100, 110, 99]) == [10.0, -10.0]


def test_average_return():
    assert average_return([10.0, -10.0, 20.0]) == pytest.approx(6.666666, rel=1e-4)


def test_analyze_stock():
    summary = analyze_stock("AAPL", [100, 110, 121])
    assert summary["ticker"] == "AAPL"
    assert summary["latest_price"] == 121
    assert summary["num_days"] == 3
    assert summary["average_daily_return"] == 10.0


def test_explain_summary_directions():
    assert "upwards" in explain_summary({"ticker": "X", "average_daily_return": 1.0})
    assert "downwards" in explain_summary({"ticker": "X", "average_daily_return": -1.0})
    assert "flat" in explain_summary({"ticker": "X", "average_daily_return": 0.0})


def test_annualized_volatility():
    assert annualized_volatility([1.0, -1.0, 1.0, -1.0]) > 0


def test_volatility_scale_buckets():
    assert volatility_scale(10)["category"] == "Low"
    assert volatility_scale(30)["category"] == "Moderate"
    assert volatility_scale(50)["category"] == "High"


def test_relative_volume():
    assert relative_volume([100, 100, 200]) == 2.0


def test_volume_signal_buckets():
    assert volume_signal(2.0)["level"] == "High"
    assert volume_signal(0.3)["level"] == "Low"
    assert volume_signal(1.0)["level"] == "Normal"


def test_institutional_signal():
    holders = pd.DataFrame({"pctChange": [0.1, 0.2, -0.1]})
    result = institutional_signal(holders)
    assert result["level"] == "Accumulating"


def test_insider_signal():
    insiders = pd.DataFrame({"Text": ["Sale at market", "Sale at market", "Purchase at open"]})
    result = insider_signal(insiders)
    assert result["level"] == "Selling"


def test_fcf_per_share():
    fcf_data = {"quarterly_fcf": [100, 100, 100, 100], "shares": 200}
    result = fcf_per_share(fcf_data)
    assert result["per_share"] == 2.0
    assert "Positive" in result["note"]


@pytest.mark.parametrize("raw,expected", [("aapl", "AAPL"), ("  msft  ", "MSFT"), ("brk.b", "BRK.B")])
def test_validate_ticker_accepts_valid(raw, expected):
    assert validate_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "???", "way-too-long-ticker", "AA PL"])
def test_validate_ticker_rejects_invalid(raw):
    with pytest.raises(InvalidTickerError):
        validate_ticker(raw)


def _make_price_history(closes, volumes):
    return pd.DataFrame({"Close": closes, "Volume": volumes})


def _patch_network_calls(price_history=None, live_quote=None, holders=None, insiders=None, fcf=None):
    live_quote = live_quote or {
        "last_price": 110.0,
        "previous_close": 100.0,
        "day_high": 112.0,
        "day_low": 99.0,
        "market_cap": 1_000_000,
    }
    price_history = price_history if price_history is not None else _make_price_history(
        [100, 105, 110], [1000, 1000, 2000]
    )
    holders = holders if holders is not None else pd.DataFrame({"pctChange": []})
    insiders = insiders if insiders is not None else pd.DataFrame({"Text": []})

    return (
        patch("stock_tool.get_live_quote", return_value=live_quote),
        patch("stock_tool.get_price_history", return_value=price_history),
        patch("stock_tool.get_institutional_summary", return_value=holders),
        patch("stock_tool.get_insider_activity", return_value=insiders),
        patch("stock_tool.get_fcf_data", return_value=fcf),
    )


@pytest.fixture(autouse=True)
def clear_report_cache():
    stock_tool._report_cache.clear()
    yield
    stock_tool._report_cache.clear()


@pytest.fixture(autouse=True)
def reset_rate_limit_cooldown():
    stock_tool._rate_limited_until = 0.0
    yield
    stock_tool._rate_limited_until = 0.0


def test_build_report_shape():
    quote_p, price_p, holders_p, insiders_p, fcf_p = _patch_network_calls()
    with quote_p, price_p, holders_p, insiders_p, fcf_p:
        report = build_report("aapl")

    assert report["ticker"] == "AAPL"
    assert report["live_quote"]["last_price"] == 110.0
    assert "trend" in report
    assert "risk" in report
    assert "volume" in report
    assert report["institutional"]["level"] == "N/A"
    assert report["insider"]["level"] == "N/A"
    assert report["fcf"]["per_share"] is None


def test_build_report_invalid_ticker_raises_before_network_call():
    with patch("stock_tool.get_live_quote") as mock_quote:
        with pytest.raises(InvalidTickerError):
            build_report("???")
    mock_quote.assert_not_called()


def test_build_report_empty_history_raises_ticker_data_error():
    quote_p, _, holders_p, insiders_p, fcf_p = _patch_network_calls()
    empty_history_p = patch("stock_tool.get_price_history", return_value=pd.DataFrame())
    with quote_p, empty_history_p, holders_p, insiders_p, fcf_p:
        with pytest.raises(TickerDataError):
            build_report("ZZZZ9")


def test_build_report_uses_cache_within_ttl():
    quote_p, price_p, holders_p, insiders_p, fcf_p = _patch_network_calls()
    with quote_p as mock_quote, price_p, holders_p, insiders_p, fcf_p:
        build_report("AAPL")
        build_report("AAPL")

    assert mock_quote.call_count == 1


def test_retry_on_failure_does_not_retry_rate_limit():
    calls = []

    @stock_tool.retry_on_failure(max_attempts=3, base_delay=0)
    def flaky():
        calls.append(1)
        raise YFRateLimitError()

    with pytest.raises(YFRateLimitError):
        flaky()

    assert len(calls) == 1  # no retries burned on a confirmed rate limit


def test_retry_on_failure_still_retries_other_errors():
    calls = []

    @stock_tool.retry_on_failure(max_attempts=3, base_delay=0)
    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("transient")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 2


def test_build_report_converts_rate_limit_error():
    with patch("stock_tool.get_live_quote", side_effect=YFRateLimitError()):
        with pytest.raises(RateLimitedError):
            build_report("AAPL")


def test_build_report_fails_fast_during_cooldown_without_network_call():
    stock_tool._note_rate_limited()
    with patch("stock_tool.get_live_quote") as mock_quote:
        with pytest.raises(RateLimitedError):
            build_report("AAPL")
    mock_quote.assert_not_called()


def test_search_tickers_returns_none_on_rate_limit():
    with patch("stock_tool._lookup_stock", side_effect=YFRateLimitError()):
        assert stock_tool.search_tickers("AAP") is None


def test_search_tickers_returns_none_during_cooldown_without_network_call():
    stock_tool._note_rate_limited()
    with patch("stock_tool._lookup_stock") as mock_lookup:
        assert stock_tool.search_tickers("AAP") is None
    mock_lookup.assert_not_called()


@pytest.fixture(autouse=True)
def clear_search_cache():
    stock_tool._search_cache.clear()
    yield
    stock_tool._search_cache.clear()


def test_search_tickers_returns_shaped_results():
    df = pd.DataFrame(
        {"shortName": ["Apple Inc.", "Advance Auto Parts Inc."], "exchange": ["NMS", "NYQ"], "quoteType": ["EQUITY", "EQUITY"]},
        index=pd.Index(["AAPL", "AAP"], name="symbol"),
    )
    with patch("stock_tool._lookup_stock", return_value=df) as mock_lookup:
        results = stock_tool.search_tickers("aap")

    mock_lookup.assert_called_once_with("AAP", 8)
    assert results == [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "quote_type": "EQUITY"},
        {"symbol": "AAP", "name": "Advance Auto Parts Inc.", "exchange": "NYQ", "quote_type": "EQUITY"},
    ]


def test_search_tickers_handles_missing_name_field():
    # Real yfinance Lookup data sometimes has a NaN (float, not None)
    # shortName for thinly-traded symbols — must not leak a raw NaN into
    # the response (it isn't valid JSON and previously caused a 500).
    df = pd.DataFrame(
        {"shortName": [float("nan")], "longName": [float("nan")], "exchange": ["NGM"], "quoteType": ["EQUITY"]},
        index=pd.Index(["ELOL"], name="symbol"),
    )
    with patch("stock_tool._lookup_stock", return_value=df):
        results = stock_tool.search_tickers("ELO")

    assert results == [{"symbol": "ELOL", "name": "", "exchange": "NGM", "quote_type": "EQUITY"}]


def test_search_tickers_empty_query_returns_empty_list_without_network_call():
    with patch("stock_tool._lookup_stock") as mock_lookup:
        assert stock_tool.search_tickers("") == []
    mock_lookup.assert_not_called()


def test_search_tickers_invalid_query_returns_empty_list_without_network_call():
    with patch("stock_tool._lookup_stock") as mock_lookup:
        assert stock_tool.search_tickers("???") == []
    mock_lookup.assert_not_called()


def test_search_tickers_network_failure_returns_none():
    with patch("stock_tool._lookup_stock", side_effect=Exception("boom")):
        assert stock_tool.search_tickers("AAP") is None


def test_search_tickers_empty_dataframe_returns_empty_list():
    with patch("stock_tool._lookup_stock", return_value=pd.DataFrame()):
        assert stock_tool.search_tickers("ZZZZ9") == []


def test_search_tickers_uses_cache_within_ttl():
    df = pd.DataFrame(
        {"shortName": ["Apple Inc."], "exchange": ["NMS"], "quoteType": ["EQUITY"]},
        index=pd.Index(["AAPL"], name="symbol"),
    )
    with patch("stock_tool._lookup_stock", return_value=df) as mock_lookup:
        stock_tool.search_tickers("AAP")
        stock_tool.search_tickers("AAP")

    assert mock_lookup.call_count == 1
