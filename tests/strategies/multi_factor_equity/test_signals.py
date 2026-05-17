import numpy as np
import pytest

from strategies.multi_factor_equity.signals import (
    composite_score,
    cross_sectional_zscore,
    low_volatility_factor,
    momentum_factor,
    reversal_factor,
    select_legs,
)


def _make_returns(n_stocks: int, n_days: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0, 0.01, (n_stocks, n_days))


def test_momentum_ranks_higher_for_strong_recent_trend():
    n_stocks = 10
    n_days = 300
    returns = _make_returns(n_stocks, n_days)
    returns[0, 21:300] += 0.005
    returns[9, 21:300] -= 0.005
    scores = momentum_factor(returns, mom_lookback=252, rev_lookback=21)
    assert scores[0] > scores[9]


def test_reversal_ranks_higher_for_negative_recent_return():
    n_stocks = 10
    n_days = 300
    returns = _make_returns(n_stocks, n_days)
    returns[0, -21:] -= 0.008
    returns[9, -21:] += 0.008
    scores = reversal_factor(returns, rev_lookback=21)
    assert scores[0] > scores[9]


def test_low_vol_ranks_higher_for_lower_volatility():
    n_stocks = 10
    n_days = 100
    rng = np.random.default_rng(42)
    returns = rng.normal(0, 0.01, (n_stocks, n_days))
    returns[0] = rng.normal(0, 0.002, n_days)
    returns[9] = rng.normal(0, 0.030, n_days)
    scores = low_volatility_factor(returns, vol_lookback=63)
    assert scores[0] > scores[9]


def test_composite_score_is_average_of_three_factor_zscores():
    n_stocks = 8
    n_days = 300
    returns = _make_returns(n_stocks, n_days, seed=7)
    mom = momentum_factor(returns, mom_lookback=252, rev_lookback=21)
    rev = reversal_factor(returns, rev_lookback=21)
    vol = low_volatility_factor(returns, vol_lookback=63)
    expected = (mom + rev + vol) / 3.0
    result = composite_score(returns, mom_lookback=252, rev_lookback=21, vol_lookback=63)
    np.testing.assert_allclose(result, expected, rtol=1e-10)


def test_cross_sectional_zscore_has_mean_zero_and_std_one():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    z = cross_sectional_zscore(values)
    assert abs(z.mean()) < 1e-10
    assert abs(z.std() - 1.0) < 1e-10


def test_cross_sectional_zscore_constant_input_returns_zeros():
    values = np.full(5, 3.14)
    z = cross_sectional_zscore(values)
    np.testing.assert_array_equal(z, np.zeros(5))


def test_select_legs_returns_correct_fraction():
    scores = np.arange(20, dtype=float)
    long_idx, short_idx = select_legs(scores, top_pct=0.20)
    assert len(long_idx) == 4
    assert len(short_idx) == 4


def test_select_legs_long_are_highest_scores():
    scores = np.array([0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6, 0.0])
    long_idx, short_idx = select_legs(scores, top_pct=0.20)
    assert set(long_idx) == {2, 6}
    assert set(short_idx) == {9, 0}


def test_momentum_factor_output_length_matches_universe():
    n_stocks = 15
    returns = _make_returns(n_stocks, 300)
    scores = momentum_factor(returns, mom_lookback=252, rev_lookback=21)
    assert len(scores) == n_stocks
