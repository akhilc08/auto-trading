import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller


def cointegration_test(
    log_prices_a: np.ndarray,
    log_prices_b: np.ndarray,
) -> tuple[float, float]:
    """
    Engle-Granger cointegration test.
    Returns (adf_pvalue, half_life_days).
    """
    X = sm.add_constant(log_prices_b)
    result = sm.OLS(log_prices_a, X).fit()
    residuals = result.resid

    adf_stat, pvalue, *_ = adfuller(residuals, maxlag=1, regression="c")
    half_life = estimate_half_life(residuals)

    return float(pvalue), float(half_life)


def estimate_half_life(spread: np.ndarray) -> float:
    """
    Fit AR(1): Δz_t = κ * z_{t-1} + ε  (κ < 0 for mean-reverting)
    Half-life = ln(2) / κ_hat.
    Returns np.inf if series is not mean-reverting.
    """
    spread_lag = spread[:-1]
    delta = np.diff(spread)
    X = sm.add_constant(spread_lag)
    result = sm.OLS(delta, X).fit()
    kappa = -result.params[1]
    if kappa <= 0:
        return np.inf
    return float(np.log(2) / kappa)


def is_valid_pair(
    log_prices_a: np.ndarray,
    log_prices_b: np.ndarray,
    pvalue_threshold: float = 0.05,
    hlife_min: float = 2.0,
    hlife_max: float = 30.0,
) -> bool:
    pvalue, half_life = cointegration_test(log_prices_a, log_prices_b)
    if pvalue >= pvalue_threshold:
        return False
    if half_life < hlife_min or half_life > hlife_max:
        return False
    return True
