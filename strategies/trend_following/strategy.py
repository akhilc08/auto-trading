import math
from dataclasses import dataclass, field

import numpy as np

from core.base_strategy import BaseStrategy
from strategies.trend_following.signals import (
    InstrumentPosition,
    SignalResult,
    compute_normalized_signal,
    compute_position_size,
    compute_realized_vol,
    compute_signal,
    update_ema,
)


@dataclass
class _InstrumentState:
    symbol: str
    fast_ema: float = 0.0
    slow_ema: float = 0.0
    atr_buf: list = field(default_factory=list)
    returns_buf: list = field(default_factory=list)
    position: InstrumentPosition = InstrumentPosition.NONE
    bars_held: int = 0
    entry_price: float = 0.0
    qty: float = 0.0
    prev_price: float = 0.0
    initialized: bool = False


class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._alpha_f = 2.0 / (config.FAST_WINDOW + 1)
        self._alpha_s = 2.0 / (config.SLOW_WINDOW + 1)
        self._states: dict[str, _InstrumentState] = {
            sym: _InstrumentState(symbol=sym) for sym in config.SYMBOLS
        }

    def on_bar(self, bars) -> None:
        for symbol, state in self._states.items():
            price = self._latest_close(bars, symbol)
            if price is None:
                continue

            if not state.initialized:
                state.fast_ema = price
                state.slow_ema = price
                state.prev_price = price
                state.initialized = True
                continue

            state.fast_ema = update_ema(state.fast_ema, price, self._alpha_f)
            state.slow_ema = update_ema(state.slow_ema, price, self._alpha_s)

            daily_move = abs(price - state.prev_price)
            state.atr_buf.append(daily_move)
            if len(state.atr_buf) > self.config.ATR_WINDOW:
                state.atr_buf.pop(0)
            atr = float(np.mean(state.atr_buf)) if state.atr_buf else 0.0

            if state.prev_price > 1e-10:
                state.returns_buf.append(math.log(price / state.prev_price))
            if len(state.returns_buf) > self.config.VOL_LOOKBACK:
                state.returns_buf.pop(0)

            state.prev_price = price

            norm_signal = compute_normalized_signal(state.fast_ema, state.slow_ema, atr)

            signal = compute_signal(
                normalized_signal=norm_signal,
                position=state.position,
                bars_held=state.bars_held,
                entry_price=state.entry_price,
                current_price=price,
                atr=atr,
                entry_threshold=self.config.ENTRY_THRESHOLD,
                atr_stop_multiple=self.config.ATR_STOP_MULTIPLE,
                max_holding_days=self.config.MAX_HOLDING_DAYS,
            )

            self.logger.info(
                f"{symbol} sig={norm_signal:.4f} pos={state.position.value} action={signal.value}"
            )

            if state.position is not InstrumentPosition.NONE and signal in (
                SignalResult.EXIT,
                SignalResult.ATR_STOP,
                SignalResult.TIME_STOP,
            ):
                self._exit(state, signal)

            if state.position is InstrumentPosition.NONE:
                if signal is SignalResult.ENTER_LONG:
                    self._enter(state, price, InstrumentPosition.LONG)
                elif signal is SignalResult.ENTER_SHORT:
                    self._enter(state, price, InstrumentPosition.SHORT)
            else:
                state.bars_held += 1

    def _enter(self, state: _InstrumentState, price: float, direction: InstrumentPosition) -> None:
        rvol = compute_realized_vol(np.array(state.returns_buf)) if state.returns_buf else 0.0
        qty = compute_position_size(price, rvol, self.config.VOL_TARGET, self.config.POSITION_SIZE_USD)
        qty = round(qty, 0)
        if qty < 1:
            return
        if direction is InstrumentPosition.LONG:
            self.order_manager.buy(state.symbol, qty)
        else:
            self.order_manager.short_sell(state.symbol, qty)
        state.position = direction
        state.entry_price = price
        state.qty = qty
        state.bars_held = 0

    def _exit(self, state: _InstrumentState, reason: SignalResult) -> None:
        self.logger.info(f"Exiting {state.symbol} reason={reason.value}")
        if state.position is InstrumentPosition.LONG:
            self.order_manager.sell(state.symbol, state.qty)
        else:
            self.order_manager.buy_to_cover(state.symbol, state.qty)
        state.position = InstrumentPosition.NONE
        state.bars_held = 0
        state.qty = 0.0
        state.entry_price = 0.0

    @staticmethod
    def _latest_close(bars, symbol: str) -> float | None:
        try:
            return float(bars[symbol][-1].close)
        except (KeyError, IndexError, TypeError):
            return None
