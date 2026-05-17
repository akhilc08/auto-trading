import pytest
from strategies.stat_arb.signals import SignalResult, PairPosition, compute_signal

DEFAULTS = dict(
    entry_zscore=2.0,
    exit_zscore=0.5,
    stoploss_zscore=3.5,
    max_holding_days=90,
)


def test_hold_when_no_position_and_z_below_entry():
    result = compute_signal(zscore=1.5, position=PairPosition.NONE, bars_held=0, **DEFAULTS)
    assert result == SignalResult.HOLD


def test_enter_long_when_z_strongly_negative():
    result = compute_signal(zscore=-2.1, position=PairPosition.NONE, bars_held=0, **DEFAULTS)
    assert result == SignalResult.ENTER_LONG


def test_enter_short_when_z_strongly_positive():
    result = compute_signal(zscore=2.1, position=PairPosition.NONE, bars_held=0, **DEFAULTS)
    assert result == SignalResult.ENTER_SHORT


def test_no_entry_exactly_at_threshold():
    result = compute_signal(zscore=2.0, position=PairPosition.NONE, bars_held=0, **DEFAULTS)
    assert result == SignalResult.HOLD


def test_exit_long_when_z_reverts_past_exit_threshold():
    result = compute_signal(zscore=0.3, position=PairPosition.LONG, bars_held=5, **DEFAULTS)
    assert result == SignalResult.EXIT


def test_exit_short_when_z_reverts_past_exit_threshold():
    result = compute_signal(zscore=-0.3, position=PairPosition.SHORT, bars_held=5, **DEFAULTS)
    assert result == SignalResult.EXIT


def test_hold_long_when_z_not_yet_reverted():
    result = compute_signal(zscore=-1.5, position=PairPosition.LONG, bars_held=5, **DEFAULTS)
    assert result == SignalResult.HOLD


def test_stop_long_when_z_goes_extreme_wrong_direction():
    result = compute_signal(zscore=-3.6, position=PairPosition.LONG, bars_held=5, **DEFAULTS)
    assert result == SignalResult.STOP


def test_stop_short_when_z_goes_extreme_wrong_direction():
    result = compute_signal(zscore=3.6, position=PairPosition.SHORT, bars_held=5, **DEFAULTS)
    assert result == SignalResult.STOP


def test_time_stop_when_holding_too_long():
    result = compute_signal(zscore=-1.0, position=PairPosition.LONG, bars_held=90, **DEFAULTS)
    assert result == SignalResult.TIME_STOP


def test_time_stop_takes_priority_over_hold():
    result = compute_signal(zscore=-1.5, position=PairPosition.SHORT, bars_held=95, **DEFAULTS)
    assert result == SignalResult.TIME_STOP


def test_stop_takes_priority_over_time_stop():
    result = compute_signal(zscore=4.0, position=PairPosition.SHORT, bars_held=95, **DEFAULTS)
    assert result == SignalResult.STOP
