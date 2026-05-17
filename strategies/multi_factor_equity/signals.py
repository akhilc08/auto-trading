import numpy as np


def cross_sectional_zscore(values: np.ndarray) -> np.ndarray:
    mean = values.mean()
    std = values.std()
    if std < 1e-10:
        return np.zeros_like(values)
    return (values - mean) / std


def momentum_factor(returns: np.ndarray, mom_lookback: int, rev_lookback: int) -> np.ndarray:
    n_stocks = returns.shape[0]
    scores = np.zeros(n_stocks)
    for i in range(n_stocks):
        r = returns[i]
        scores[i] = r[-mom_lookback:-rev_lookback].sum()
    return cross_sectional_zscore(scores)


def reversal_factor(returns: np.ndarray, rev_lookback: int) -> np.ndarray:
    n_stocks = returns.shape[0]
    scores = np.zeros(n_stocks)
    for i in range(n_stocks):
        scores[i] = -returns[i][-rev_lookback:].sum()
    return cross_sectional_zscore(scores)


def low_volatility_factor(returns: np.ndarray, vol_lookback: int) -> np.ndarray:
    n_stocks = returns.shape[0]
    scores = np.zeros(n_stocks)
    for i in range(n_stocks):
        scores[i] = -returns[i][-vol_lookback:].std()
    return cross_sectional_zscore(scores)


def composite_score(
    returns: np.ndarray,
    mom_lookback: int,
    rev_lookback: int,
    vol_lookback: int,
) -> np.ndarray:
    mom = momentum_factor(returns, mom_lookback, rev_lookback)
    rev = reversal_factor(returns, rev_lookback)
    vol = low_volatility_factor(returns, vol_lookback)
    return (mom + rev + vol) / 3.0


def select_legs(scores: np.ndarray, top_pct: float) -> tuple[np.ndarray, np.ndarray]:
    n = len(scores)
    k = max(1, int(round(n * top_pct)))
    ranked = np.argsort(scores)
    long_idx = ranked[-k:]
    short_idx = ranked[:k]
    return long_idx, short_idx
