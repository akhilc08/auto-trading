from enum import Enum


class Position(Enum):
    NONE = "none"
    LONG = "long"
    SHORT = "short"


class Signal(Enum):
    HOLD = "hold"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    STOP = "stop"
    TIME_STOP = "time_stop"


def compute_signal(
    zscore: float,
    position: Position,
    bars_held: int,
    entry_zscore: float,
    exit_zscore: float,
    stoploss_zscore: float,
    max_holding_days: int,
) -> Signal:
    if position is Position.NONE:
        if zscore < -entry_zscore:
            return Signal.ENTER_LONG
        if zscore > entry_zscore:
            return Signal.ENTER_SHORT
        return Signal.HOLD

    if position is Position.LONG:
        if zscore <= -stoploss_zscore:
            return Signal.STOP
        if bars_held >= max_holding_days:
            return Signal.TIME_STOP
        if zscore >= -exit_zscore:
            return Signal.EXIT

    if position is Position.SHORT:
        if zscore >= stoploss_zscore:
            return Signal.STOP
        if bars_held >= max_holding_days:
            return Signal.TIME_STOP
        if zscore <= exit_zscore:
            return Signal.EXIT

    return Signal.HOLD
