import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from strategies.post_earnings_drift.signals import get_earnings_surprise


def _make_ticker_mock(df: pd.DataFrame) -> MagicMock:
    mock_ticker = MagicMock()
    mock_ticker.earnings_dates = df
    return mock_ticker


def test_positive_surprise_found():
    now_utc = pd.Timestamp.now(tz="UTC")
    index = pd.DatetimeIndex([now_utc - pd.Timedelta(days=1)])
    df = pd.DataFrame({"Surprise(%)": [12.5]}, index=index)
    mock_ticker = _make_ticker_mock(df)
    with patch("strategies.post_earnings_drift.signals.yf.Ticker", return_value=mock_ticker):
        result = get_earnings_surprise("AAPL")
    assert result == 12.5


def test_negative_surprise_found():
    now_utc = pd.Timestamp.now(tz="UTC")
    index = pd.DatetimeIndex([now_utc - pd.Timedelta(days=1)])
    df = pd.DataFrame({"Surprise(%)": [-8.3]}, index=index)
    mock_ticker = _make_ticker_mock(df)
    with patch("strategies.post_earnings_drift.signals.yf.Ticker", return_value=mock_ticker):
        result = get_earnings_surprise("AAPL")
    assert result == -8.3


def test_no_recent_earnings_returns_none():
    now_utc = pd.Timestamp.now(tz="UTC")
    index = pd.DatetimeIndex([now_utc - pd.Timedelta(days=10)])
    df = pd.DataFrame({"Surprise(%)": [5.0]}, index=index)
    mock_ticker = _make_ticker_mock(df)
    with patch("strategies.post_earnings_drift.signals.yf.Ticker", return_value=mock_ticker):
        result = get_earnings_surprise("AAPL")
    assert result is None


def test_empty_dataframe_returns_none():
    df = pd.DataFrame({"Surprise(%)": []})
    mock_ticker = _make_ticker_mock(df)
    with patch("strategies.post_earnings_drift.signals.yf.Ticker", return_value=mock_ticker):
        result = get_earnings_surprise("AAPL")
    assert result is None


def test_fallback_to_estimate_computation():
    now_utc = pd.Timestamp.now(tz="UTC")
    index = pd.DatetimeIndex([now_utc - pd.Timedelta(days=1)])
    df = pd.DataFrame(
        {"EPS Estimate": [1.0], "Reported EPS": [1.15]},
        index=index,
    )
    mock_ticker = _make_ticker_mock(df)
    with patch("strategies.post_earnings_drift.signals.yf.Ticker", return_value=mock_ticker):
        result = get_earnings_surprise("AAPL")
    assert result == pytest.approx(15.0)
