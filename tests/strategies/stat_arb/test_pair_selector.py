import numpy as np
import pytest
from strategies.stat_arb.pair_selector import cointegration_test, estimate_half_life, is_valid_pair


def _make_cointegrated(n: int, phi: float, seed: int):
    np.random.seed(seed)
    log_b = np.cumsum(np.random.normal(0, 0.01, n)) + 4.6
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = phi * spread[i - 1] + np.random.normal(0, 0.005)
    log_a = log_b + spread
    return log_a, log_b


def test_cointegrated_pair_has_low_pvalue():
    log_a, log_b = _make_cointegrated(n=500, phi=0.85, seed=42)
    pvalue, half_life = cointegration_test(log_a, log_b)
    assert pvalue < 0.05


def test_non_cointegrated_pair_has_high_pvalue():
    np.random.seed(12345)
    log_a = np.cumsum(np.random.normal(0, 0.01, 2000)) + 4.0
    log_b = np.cumsum(np.random.normal(0, 0.01, 2000)) + 4.5
    pvalue, _ = cointegration_test(log_a, log_b)
    assert pvalue > 0.05


def test_half_life_near_expected_for_known_phi():
    log_a, log_b = _make_cointegrated(n=800, phi=0.85, seed=7)
    pvalue, half_life = cointegration_test(log_a, log_b)
    assert 2.0 < half_life < 12.0


def test_estimate_half_life_for_fast_reverter():
    np.random.seed(10)
    spread = np.zeros(500)
    for i in range(1, 500):
        spread[i] = 0.75 * spread[i - 1] + np.random.normal(0, 0.1)
    hl = estimate_half_life(spread)
    assert 1.0 < hl < 6.0


def test_estimate_half_life_returns_inf_for_unit_root():
    np.random.seed(99)
    random_walk = np.cumsum(np.random.normal(0, 1, 300))
    hl = estimate_half_life(random_walk)
    assert hl == np.inf or hl > 30


def test_is_valid_pair_passes_good_pair():
    log_a, log_b = _make_cointegrated(n=500, phi=0.85, seed=42)
    assert is_valid_pair(log_a, log_b, pvalue_threshold=0.05, hlife_min=2.0, hlife_max=30.0)


def test_is_valid_pair_rejects_slow_reverter():
    # phi=0.999 → theoretical half_life ≈ 693 days; even with estimation bias should far exceed hlife_max=30
    log_a, log_b = _make_cointegrated(n=2000, phi=0.999, seed=42)
    assert not is_valid_pair(log_a, log_b, pvalue_threshold=0.05, hlife_min=2.0, hlife_max=30.0)
