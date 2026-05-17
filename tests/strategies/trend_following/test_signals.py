import math
import numpy as np
import pytest

from strategies.trend_following.signals import (
    InstrumentPosition,
    SignalResult,
    compute_fast_ema,
    compute_signal,
    compute_normalized_signal,
    compute_realized_vol,
    compute_position_size,
    update_ema,
)


def test_fast_ema_converges_faster_than_slow():
    prices = np.ones(200) * 100.0
    prices[100:] = 120.0

    fast_ema = prices[0]
    slow_ema = prices[0]
    alpha_f = 2.0 / (20 + 1)
    alpha_s = 2.0 / (60 + 1)

    for p in prices[1:]:
        fast_ema = update_ema(fast_ema, p, alpha_f)
        slow_ema = update_ema(slow_ema, p, alpha_s)

    assert abs(fast_ema - 120.0) < abs(slow_ema - 120.0), (
        "fast EMA should be closer to new price than slow EMA"
    )


def test_normalized_signal_near_zero_for_flat_price():
    prices = np.ones(200) * 100.0
    fast_ema = prices[0]
    slow_ema = prices[0]
    alpha_f = 2.0 / (20 + 1)
    alpha_s = 2.0 / (60 + 1)
    atr = 0.0

    for i in range(1, len(prices)):
        fast_ema = update_ema(fast_ema, prices[i], alpha_f)
        slow_ema = update_ema(slow_ema, prices[i], alpha_s)
        atr = abs(prices[i] - prices[i - 1])

    sig = compute_normalized_signal(fast_ema, slow_ema, atr if atr > 0 else 1e-10)
    assert abs(sig) < 0.01, f"signal should be near zero for flat prices, got {sig}"


def test_positive_signal_for_uptrending_price():
    n = 200
    prices = np.linspace(100.0, 150.0, n)
    fast_ema = prices[0]
    slow_ema = prices[0]
    alpha_f = 2.0 / (10 + 1)
    alpha_s = 2.0 / (30 + 1)
    atr_buf = []

    for i in range(1, n):
        fast_ema = update_ema(fast_ema, prices[i], alpha_f)
        slow_ema = update_ema(slow_ema, prices[i], alpha_s)
        atr_buf.append(abs(prices[i] - prices[i - 1]))
        if len(atr_buf) > 14:
            atr_buf.pop(0)

    atr = float(np.mean(atr_buf))
    sig = compute_normalized_signal(fast_ema, slow_ema, atr)
    assert sig > 0, f"signal should be positive for uptrend, got {sig}"


def test_negative_signal_for_downtrending_price():
    n = 200
    prices = np.linspace(150.0, 100.0, n)
    fast_ema = prices[0]
    slow_ema = prices[0]
    alpha_f = 2.0 / (10 + 1)
    alpha_s = 2.0 / (30 + 1)
    atr_buf = []

    for i in range(1, n):
        fast_ema = update_ema(fast_ema, prices[i], alpha_f)
        slow_ema = update_ema(slow_ema, prices[i], alpha_s)
        atr_buf.append(abs(prices[i] - prices[i - 1]))
        if len(atr_buf) > 14:
            atr_buf.pop(0)

    atr = float(np.mean(atr_buf))
    sig = compute_normalized_signal(fast_ema, slow_ema, atr)
    assert sig < 0, f"signal should be negative for downtrend, got {sig}"


def test_atr_is_always_positive():
    rng = np.random.default_rng(42)
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 200)))
    atr_buf = []

    for i in range(1, len(prices)):
        atr_buf.append(abs(prices[i] - prices[i - 1]))
        if len(atr_buf) > 14:
            atr_buf.pop(0)
        atr = float(np.mean(atr_buf))
        assert atr >= 0.0, f"ATR must be non-negative, got {atr} at bar {i}"


def test_vol_targeting_scales_down_in_high_vol():
    price = 100.0

    low_vol_returns = np.array([0.001] * 20)
    high_vol_returns = np.array([0.05, -0.05] * 10)

    low_rvol = compute_realized_vol(low_vol_returns)
    high_rvol = compute_realized_vol(high_vol_returns)

    qty_low = compute_position_size(price, low_rvol, 0.15, 10_000)
    qty_high = compute_position_size(price, high_rvol, 0.15, 10_000)

    assert qty_high < qty_low, (
        f"high vol ({high_rvol:.2%}) should give smaller position than low vol ({low_rvol:.2%}): "
        f"qty_high={qty_high:.2f} qty_low={qty_low:.2f}"
    )


def test_enter_long_when_signal_above_threshold():
    sig = compute_signal(
        normalized_signal=0.05,
        position=InstrumentPosition.NONE,
        bars_held=0,
        entry_price=0.0,
        current_price=100.0,
        atr=1.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.ENTER_LONG


def test_enter_short_when_signal_below_negative_threshold():
    sig = compute_signal(
        normalized_signal=-0.05,
        position=InstrumentPosition.NONE,
        bars_held=0,
        entry_price=0.0,
        current_price=100.0,
        atr=1.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.ENTER_SHORT


def test_hold_when_signal_below_threshold():
    sig = compute_signal(
        normalized_signal=0.005,
        position=InstrumentPosition.NONE,
        bars_held=0,
        entry_price=0.0,
        current_price=100.0,
        atr=1.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.HOLD


def test_exit_long_when_signal_crosses_zero():
    sig = compute_signal(
        normalized_signal=-0.001,
        position=InstrumentPosition.LONG,
        bars_held=5,
        entry_price=100.0,
        current_price=101.0,
        atr=1.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.EXIT


def test_atr_stop_long():
    sig = compute_signal(
        normalized_signal=0.02,
        position=InstrumentPosition.LONG,
        bars_held=5,
        entry_price=100.0,
        current_price=93.0,
        atr=2.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.ATR_STOP


def test_time_stop_triggers_at_max_holding():
    sig = compute_signal(
        normalized_signal=0.05,
        position=InstrumentPosition.LONG,
        bars_held=60,
        entry_price=100.0,
        current_price=102.0,
        atr=1.0,
        entry_threshold=0.01,
        atr_stop_multiple=3.0,
        max_holding_days=60,
    )
    assert sig is SignalResult.TIME_STOP
