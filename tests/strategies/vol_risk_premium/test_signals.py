import math
from unittest.mock import patch

import pytest

from strategies.vol_risk_premium.signals import Signal, compute_signal, fetch_vix, realized_vol


def _sig(vix, vix3m, rv, vix_crisis=35.0, vix_caution=25.0, entry=0.40, full=0.70):
    signal, composite = compute_signal(
        vix=vix,
        vix3m=vix3m,
        rv=rv,
        vix_crisis=vix_crisis,
        vix_caution=vix_caution,
        composite_entry=entry,
        composite_full=full,
    )
    return signal, composite


def test_strong_signal_high_vrp():
    # IV=0.18, RV=0.08 → vrp_spread=0.10, vrp_score=1.0; ts_ratio=1.12 → ts_score=1.0; composite=1.0
    signal, composite = _sig(vix=18.0, vix3m=20.16, rv=0.08)
    assert signal == Signal.STRONG
    assert composite >= 0.70


def test_no_signal_vix_crisis():
    # VIX=40 exceeds crisis threshold → always NONE regardless of spread
    signal, _ = _sig(vix=40.0, vix3m=44.0, rv=0.08)
    assert signal == Signal.NONE


def test_moderate_signal_low_composite():
    # vrp_spread = 0.18 - 0.14 = 0.04 → vrp_score=0.5; ts_ratio=1.05 → ts_score=0.5; composite=0.5
    signal, composite = _sig(vix=18.0, vix3m=18.9, rv=0.14)
    assert signal == Signal.MODERATE
    assert 0.40 <= composite < 0.70


def test_no_signal_backwardation():
    # VIX3M < VIX → ts_ratio < 1.0 → ts_score=0; low vrp spread → composite < ENTRY
    # vrp_spread = 0.18 - 0.175 = 0.005 → vrp_score=0.0625; ts_score=0; composite=0.0375
    signal, composite = _sig(vix=18.0, vix3m=17.0, rv=0.175)
    assert signal == Signal.NONE
    assert composite < 0.40


def test_realized_vol_calculation():
    # Daily return of 0.01 for 22 days → RV = sqrt(252) * 0.01 ≈ 0.15874
    returns = [0.01] * 22
    rv = realized_vol(returns)
    expected = math.sqrt(252) * 0.01
    assert abs(rv - expected) < 1e-6


def test_fetch_vix_returns_none_on_failure():
    # Must NOT fabricate (18, 20) — that drives real short-vol BUYs on fake data.
    with patch("strategies.vol_risk_premium.signals.yf.download", side_effect=Exception("net")):
        assert fetch_vix() == (None, None)


def test_fetch_vix_handles_multiindex_columns():
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({("Close", "^VIX"): [10.0, 11.0, 13.0]}, index=idx)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    with patch("strategies.vol_risk_premium.signals.yf.download", return_value=df):
        vix, vix3m = fetch_vix()
    assert vix == 13.0 and vix3m == 13.0


def test_caution_zone_caps_at_moderate():
    # VIX=28 (caution zone), very high composite that would otherwise be STRONG
    # vrp_spread=0.28-0.08=0.20→vrp_score=1.0; ts_ratio=1.12→ts_score=1.0; composite=1.0
    # But VIX>caution → capped at MODERATE
    signal, composite = _sig(vix=28.0, vix3m=31.36, rv=0.08)
    assert signal == Signal.MODERATE
    assert composite >= 0.70
