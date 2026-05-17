import numpy as np


class KalmanSpread:
    """
    Tracks a time-varying hedge ratio β and intercept α for a log-price pair.

    State θ = [β, α] evolves as a random walk (process noise W).
    Each call to update() returns the normalized innovation — the basis for
    the trading z-score without requiring a fixed rolling window.
    """

    def __init__(self, delta: float = 1e-4, obs_noise: float = 1e-3):
        self._theta = np.array([1.0, 0.0])
        self._P = np.eye(2)
        self._W = (delta / (1.0 - delta)) * np.eye(2)
        self._V = obs_noise

    def update(self, log_price_a: float, log_price_b: float) -> tuple[float, float]:
        F = np.array([log_price_b, 1.0])

        P_pred = self._P + self._W

        e = log_price_a - float(F @ self._theta)
        Q = float(F @ P_pred @ F) + self._V

        K = P_pred @ F / Q

        self._theta = self._theta + K * e
        self._P = (np.eye(2) - np.outer(K, F)) @ P_pred

        return float(e), float(np.sqrt(Q))

    @property
    def beta(self) -> float:
        return float(self._theta[0])

    @property
    def alpha(self) -> float:
        return float(self._theta[1])
