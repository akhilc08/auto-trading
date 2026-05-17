from enum import Enum


class PairPosition(Enum):
    NONE = "none"
    LONG = "long"
    SHORT = "short"


class SignalResult(Enum):
    HOLD = "hold"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    STOP = "stop"
    TIME_STOP = "time_stop"


def compute_signal(
    zscore: float,
    position: PairPosition,
    bars_held: int,
    entry_zscore: float,
    exit_zscore: float,
    stoploss_zscore: float,
    max_holding_days: int,
) -> SignalResult:
    if position is PairPosition.NONE:
        if zscore < -entry_zscore:
            return SignalResult.ENTER_LONG
        if zscore > entry_zscore:
            return SignalResult.ENTER_SHORT
        return SignalResult.HOLD

    if position is PairPosition.LONG:
        if zscore <= -stoploss_zscore:
            return SignalResult.STOP
        if bars_held >= max_holding_days:
            return SignalResult.TIME_STOP
        if zscore >= -exit_zscore:
            return SignalResult.EXIT

    if position is PairPosition.SHORT:
        if zscore >= stoploss_zscore:
            return SignalResult.STOP
        if bars_held >= max_holding_days:
            return SignalResult.TIME_STOP
        if zscore <= exit_zscore:
            return SignalResult.EXIT

    return SignalResult.HOLD
