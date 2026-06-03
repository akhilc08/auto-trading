from unittest.mock import patch

import pytest

from strategies.regime_switching.signals import Regime, detect_regime, fetch_vix


class _Cfg:
    VIX_CRISIS = 30.0
    VIX_RISK_OFF = 20.0


def _rising_closes(n: int = 210, daily_drift: float = 0.0005) -> list[float]:
    price = 100.0
    closes = []
    for _ in range(n):
        price *= 1 + daily_drift
        closes.append(price)
    return closes


def _crash_closes(n: int = 200) -> list[float]:
    """First half rises, second half drops sharply so last price is well below 200d MA."""
    first = [100.0 + i * 0.2 for i in range(n // 2)]
    second = [first[-1] - (j + 1) * 0.5 for j in range(n - n // 2)]
    return first + second


def test_insufficient_history_returns_mean_reverting():
    state = detect_regime(vix=15.0, vix3m=16.0, spy_closes=[100.0] * 20, config=_Cfg())
    assert state.regime == Regime.MEAN_REVERTING
    assert state.confidence == pytest.approx(0.3)


def test_crisis_regime():
    closes = _rising_closes(200, daily_drift=0.0001)
    state = detect_regime(vix=35.0, vix3m=32.0, spy_closes=closes, config=_Cfg())
    assert state.regime == Regime.CRISIS
    assert state.confidence > 0.6


def test_risk_off_regime_high_vix():
    closes = _rising_closes(200, daily_drift=0.0001)
    state = detect_regime(vix=22.0, vix3m=23.0, spy_closes=closes, config=_Cfg())
    assert state.regime == Regime.RISK_OFF


def test_risk_off_regime_spy_below_ma():
    closes = _crash_closes(200)
    state = detect_regime(vix=16.0, vix3m=17.0, spy_closes=closes, config=_Cfg())
    assert state.regime == Regime.RISK_OFF


def test_trending_regime():
    closes = _rising_closes(210, daily_drift=0.0005)
    state = detect_regime(vix=13.0, vix3m=14.0, spy_closes=closes, config=_Cfg())
    assert state.regime == Regime.TRENDING
    assert state.confidence > 0.5


def test_mean_reverting_regime_flat_prices():
    closes = [100.0] * 200
    state = detect_regime(vix=15.0, vix3m=15.5, spy_closes=closes, config=_Cfg())
    assert state.regime == Regime.MEAN_REVERTING


def test_fetch_vix_returns_none_on_failure():
    # Must NOT fabricate calm (18, 20) values — that silently disables VIX-driven
    # RISK_OFF/CRISIS detection. Return None so the caller skips the bar.
    with patch("strategies.regime_switching.signals.yf.download", side_effect=Exception("network")):
        vix, vix3m = fetch_vix()
    assert vix is None and vix3m is None


def test_fetch_vix_handles_multiindex_columns():
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({("Close", "^VIX"): [10.0, 11.0, 12.5]}, index=idx)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    with patch("strategies.regime_switching.signals.yf.download", return_value=df):
        vix, vix3m = fetch_vix()
    assert vix == 12.5 and vix3m == 12.5
