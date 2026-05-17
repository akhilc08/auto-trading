import numpy as np
import pytest
import statsmodels.api as sm

from strategies.market_neutral.signals import Position, Signal, compute_signal

DEFAULTS = dict(
    entry_zscore=2.0,
    exit_zscore=0.5,
    stoploss_zscore=3.5,
    max_holding_days=60,
)


def test_enter_long_when_z_strongly_negative():
    result = compute_signal(zscore=-2.1, position=Position.NONE, bars_held=0, **DEFAULTS)
    assert result == Signal.ENTER_LONG


def test_enter_short_when_z_strongly_positive():
    result = compute_signal(zscore=2.1, position=Position.NONE, bars_held=0, **DEFAULTS)
    assert result == Signal.ENTER_SHORT


def test_exit_long_when_z_reverts():
    result = compute_signal(zscore=0.3, position=Position.LONG, bars_held=5, **DEFAULTS)
    assert result == Signal.EXIT


def test_stop_long_when_z_extreme_wrong_direction():
    result = compute_signal(zscore=-3.6, position=Position.LONG, bars_held=5, **DEFAULTS)
    assert result == Signal.STOP


def test_time_stop_when_holding_too_long():
    result = compute_signal(zscore=-1.0, position=Position.LONG, bars_held=60, **DEFAULTS)
    assert result == Signal.TIME_STOP


def test_hold_when_no_position_and_z_below_entry():
    result = compute_signal(zscore=1.5, position=Position.NONE, bars_held=0, **DEFAULTS)
    assert result == Signal.HOLD


def test_exit_short_when_z_reverts():
    result = compute_signal(zscore=-0.3, position=Position.SHORT, bars_held=5, **DEFAULTS)
    assert result == Signal.EXIT


def test_stop_short_when_z_extreme_wrong_direction():
    result = compute_signal(zscore=3.6, position=Position.SHORT, bars_held=5, **DEFAULTS)
    assert result == Signal.STOP


def test_hold_long_when_z_not_yet_reverted():
    result = compute_signal(zscore=-1.5, position=Position.LONG, bars_held=5, **DEFAULTS)
    assert result == Signal.HOLD


def test_time_stop_takes_priority_over_hold():
    result = compute_signal(zscore=-1.5, position=Position.SHORT, bars_held=65, **DEFAULTS)
    assert result == Signal.TIME_STOP


def test_ols_beta_estimation_close_to_true():
    rng = np.random.default_rng(0)
    n = 500
    true_beta = 1.2
    log_market = np.cumsum(rng.normal(0, 0.01, n))
    noise = rng.normal(0, 0.005, n)
    log_stock = true_beta * log_market + noise
    X = sm.add_constant(log_market)
    result = sm.OLS(log_stock, X).fit()
    beta_hat = result.params[1]
    assert abs(beta_hat - true_beta) < 0.1


def test_no_entry_exactly_at_threshold():
    result = compute_signal(zscore=2.0, position=Position.NONE, bars_held=0, **DEFAULTS)
    assert result == Signal.HOLD
