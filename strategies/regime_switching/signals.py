from dataclasses import dataclass
from enum import Enum

import yfinance as yf


class Regime(Enum):
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"


@dataclass
class RegimeState:
    regime: Regime
    vix: float
    ts_ratio: float
    spy_vs_ma200: float   # (SPY / 200d MA) - 1
    spy_30d_ret: float
    confidence: float


def fetch_vix() -> tuple[float, float]:
    """(VIX, VIX3M). Falls back to (18.0, 20.0) on failure."""
    try:
        vix = float(
            yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=False)
            ["Close"].dropna().iloc[-1]
        )
        vix3m = float(
            yf.download("^VIX3M", period="5d", interval="1d", progress=False, auto_adjust=False)
            ["Close"].dropna().iloc[-1]
        )
        return vix, vix3m
    except Exception:
        return 18.0, 20.0


def detect_regime(
    vix: float,
    vix3m: float,
    spy_closes: list[float],
    config,
) -> RegimeState:
    ts_ratio = vix3m / vix if vix > 1 else 1.0

    if len(spy_closes) < 30:
        return RegimeState(Regime.MEAN_REVERTING, vix, ts_ratio, 0.0, 0.0, 0.3)

    spy_now = spy_closes[-1]
    window = min(200, len(spy_closes))
    ma200 = sum(spy_closes[-window:]) / window
    spy_vs_ma = spy_now / ma200 - 1.0

    lookback = min(31, len(spy_closes))
    spy_30d = spy_now / spy_closes[-lookback] - 1.0

    if vix >= config.VIX_CRISIS:
        regime = Regime.CRISIS
        confidence = min(1.0, 0.6 + (vix - config.VIX_CRISIS) / 15.0)
    elif vix >= config.VIX_RISK_OFF or spy_vs_ma < -0.05:
        regime = Regime.RISK_OFF
        confidence = 0.5 + 0.3 * min(1.0, (vix - config.VIX_RISK_OFF) / 10.0)
        confidence = max(0.4, confidence)
    elif spy_vs_ma > 0.02 and spy_30d > 0.0 and ts_ratio > 1.04:
        regime = Regime.TRENDING
        confidence = min(1.0, 0.5 + spy_vs_ma * 2 + (ts_ratio - 1.04) * 5)
    else:
        regime = Regime.MEAN_REVERTING
        confidence = 0.4

    return RegimeState(
        regime=regime,
        vix=vix,
        ts_ratio=ts_ratio,
        spy_vs_ma200=spy_vs_ma,
        spy_30d_ret=spy_30d,
        confidence=confidence,
    )
