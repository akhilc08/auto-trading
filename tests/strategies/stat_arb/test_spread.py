import numpy as np
import pytest
from strategies.stat_arb.spread import KalmanSpread


def test_kalman_spread_initializes_with_beta_one():
    spread = KalmanSpread(delta=1e-4, obs_noise=1e-3)
    assert spread.beta == pytest.approx(1.0)
    assert spread.alpha == pytest.approx(0.0)


def test_update_returns_float_innovation_and_positive_std():
    spread = KalmanSpread()
    e, e_std = spread.update(log_price_a=4.6, log_price_b=4.6)
    assert isinstance(e, float)
    assert e_std > 0.0


def test_update_innovation_is_zero_for_perfect_equilibrium():
    spread = KalmanSpread(delta=1e-5, obs_noise=1e-4)
    np.random.seed(0)
    log_b = np.cumsum(np.random.normal(0, 0.01, 300)) + 4.6
    log_a = 1.0 * log_b
    innovations = [spread.update(a, b)[0] for a, b in zip(log_a, log_b)]
    assert abs(np.mean(innovations[100:])) < 0.01


def test_beta_converges_toward_true_ratio():
    spread = KalmanSpread(delta=1e-3, obs_noise=1e-3)
    np.random.seed(42)
    log_b = np.cumsum(np.random.normal(0, 0.01, 300)) + 4.0
    log_a = 0.5 * log_b + np.random.normal(0, 0.003, 300)
    for a, b in zip(log_a, log_b):
        spread.update(a, b)
    assert 0.35 < spread.beta < 0.65


def test_e_std_is_always_positive_after_many_updates():
    spread = KalmanSpread()
    np.random.seed(7)
    log_b = np.cumsum(np.random.normal(0, 0.01, 200)) + 4.0
    log_a = log_b + np.random.normal(0, 0.01, 200)
    for a, b in zip(log_a, log_b):
        _, e_std = spread.update(a, b)
        assert e_std > 0.0
