import math
from enum import Enum

import yfinance as yf


class Signal(Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    NONE = "none"


def _last_close(symbol: str) -> float:
    df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=False)
    close = df["Close"]
    # Modern yfinance returns MultiIndex columns even for a single ticker, which
    # makes df["Close"] a DataFrame; take its first (only) column.
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return float(close.dropna().iloc[-1])


def fetch_vix() -> tuple[float | None, float | None]:
    """(VIX, VIX3M), or (None, None) when the data is unavailable.

    Returns None on failure rather than fabricating 'calm market' values — the
    caller must skip the bar, not trade short-vol on hardcoded inputs.
    """
    try:
        return _last_close("^VIX"), _last_close("^VIX3M")
    except Exception:
        return None, None


def realized_vol(log_returns: list[float]) -> float:
    if len(log_returns) < 1:
        return 0.0
    mean_sq = sum(r * r for r in log_returns) / len(log_returns)
    return math.sqrt(252 * mean_sq)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_signal(
    vix: float,
    vix3m: float,
    rv: float,
    vix_crisis: float,
    vix_caution: float,
    composite_entry: float,
    composite_full: float,
) -> tuple[Signal, float]:
    if vix > vix_crisis:
        return Signal.NONE, 0.0

    iv = vix / 100.0
    vrp_spread = iv - rv
    vrp_score = _clamp(vrp_spread / 0.08, 0.0, 1.0)

    ts_ratio = vix3m / vix if vix > 1e-10 else 1.0
    ts_score = _clamp((ts_ratio - 1.0) / 0.10, 0.0, 1.0)

    composite = 0.6 * vrp_score + 0.4 * ts_score

    if vix > vix_caution:
        if composite >= composite_full:
            return Signal.MODERATE, composite
        if composite >= composite_entry:
            return Signal.MODERATE, composite
        return Signal.NONE, composite

    if composite >= composite_full:
        return Signal.STRONG, composite
    if composite >= composite_entry:
        return Signal.MODERATE, composite
    return Signal.NONE, composite
