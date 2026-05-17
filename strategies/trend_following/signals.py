import math
from enum import Enum

import numpy as np


class InstrumentPosition(Enum):
    NONE = "none"
    LONG = "long"
    SHORT = "short"


class SignalResult(Enum):
    HOLD = "hold"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    ATR_STOP = "atr_stop"
    TIME_STOP = "time_stop"


def compute_fast_ema(prices: np.ndarray, window: int) -> np.ndarray:
    alpha = 2.0 / (window + 1)
    ema = np.empty(len(prices))
    ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
    return ema


def update_ema(prev_ema: float, price: float, alpha: float) -> float:
    return alpha * price + (1 - alpha) * prev_ema


def compute_atr(prices: np.ndarray, window: int) -> np.ndarray:
    n = len(prices)
    atr = np.empty(n)
    atr[0] = 0.0
    for i in range(1, n):
        atr[i] = abs(prices[i] - prices[i - 1])
    result = np.empty(n)
    result[0] = atr[0]
    for i in range(1, n):
        start = max(0, i - window + 1)
        result[i] = float(np.mean(atr[start : i + 1]))
    return result


def compute_normalized_signal(
    fast_ema: float,
    slow_ema: float,
    atr: float,
) -> float:
    if atr < 1e-10 or slow_ema < 1e-10:
        return 0.0
    return (fast_ema - slow_ema) / (atr * slow_ema)


def compute_realized_vol(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns) * math.sqrt(252))


def compute_position_size(
    price: float,
    realized_vol: float,
    vol_target: float,
    position_size_usd: float,
) -> float:
    if realized_vol > 1e-10:
        size_multiplier = vol_target / realized_vol
    else:
        size_multiplier = 1.0
    return position_size_usd * size_multiplier / price


def compute_signal(
    normalized_signal: float,
    position: InstrumentPosition,
    bars_held: int,
    entry_price: float,
    current_price: float,
    atr: float,
    entry_threshold: float,
    atr_stop_multiple: float,
    max_holding_days: int,
) -> SignalResult:
    if position is InstrumentPosition.NONE:
        if normalized_signal > entry_threshold:
            return SignalResult.ENTER_LONG
        if normalized_signal < -entry_threshold:
            return SignalResult.ENTER_SHORT
        return SignalResult.HOLD

    if position is InstrumentPosition.LONG:
        if bars_held >= max_holding_days:
            return SignalResult.TIME_STOP
        if atr > 1e-10 and (current_price - entry_price) < -(atr_stop_multiple * atr):
            return SignalResult.ATR_STOP
        if normalized_signal <= 0.0:
            return SignalResult.EXIT

    if position is InstrumentPosition.SHORT:
        if bars_held >= max_holding_days:
            return SignalResult.TIME_STOP
        if atr > 1e-10 and (current_price - entry_price) > (atr_stop_multiple * atr):
            return SignalResult.ATR_STOP
        if normalized_signal >= 0.0:
            return SignalResult.EXIT

    return SignalResult.HOLD
