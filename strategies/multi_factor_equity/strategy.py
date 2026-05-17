from collections import deque

import numpy as np

from core.base_strategy import BaseStrategy
from strategies.multi_factor_equity.signals import composite_score, select_legs


class MultiFactorStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._initialized = False
        self._day_counter = 0
        self._max_buf = max(config.MOM_LOOKBACK, config.VOL_LOOKBACK) + 10
        self._return_history: dict[str, deque] = {
            sym: deque(maxlen=self._max_buf) for sym in config.SYMBOLS
        }
        self._prev_close: dict[str, float] = {}
        self._current_positions: dict[str, tuple[float, int, float]] = {}

    def on_bar(self, bars) -> None:
        closes = self._extract_closes(bars)
        if not closes:
            return

        for sym, price in closes.items():
            if sym in self._prev_close and self._prev_close[sym] > 0:
                log_ret = np.log(price / self._prev_close[sym])
                self._return_history[sym].append(log_ret)
            self._prev_close[sym] = price

        self._day_counter += 1

        if self._day_counter % self.config.REBALANCE_FREQ != 0:
            return

        min_history = max(self.config.MOM_LOOKBACK, self.config.VOL_LOOKBACK)
        ready_symbols = [
            sym for sym in self.config.SYMBOLS
            if len(self._return_history[sym]) >= min_history and sym in closes
        ]

        if len(ready_symbols) < 4:
            return

        returns_matrix = np.array([
            list(self._return_history[sym]) for sym in ready_symbols
        ])

        scores = composite_score(
            returns_matrix,
            mom_lookback=self.config.MOM_LOOKBACK,
            rev_lookback=self.config.REV_LOOKBACK,
            vol_lookback=self.config.VOL_LOOKBACK,
        )

        long_idx, short_idx = select_legs(scores, self.config.TOP_PCT)

        for sym, (qty, direction, _) in list(self._current_positions.items()):
            if direction == 1:
                self.order_manager.sell(sym, qty)
            else:
                self.order_manager.buy_to_cover(sym, qty)
        self._current_positions = {}

        for idx in long_idx:
            sym = ready_symbols[idx]
            price = closes[sym]
            qty = round(self.config.POSITION_SIZE_USD / price, 0)
            if qty < 1:
                continue
            self.order_manager.buy(sym, qty)
            self._current_positions[sym] = (qty, 1, price)
            self.logger.info(f"LONG {sym} qty={qty} price={price:.2f}")

        for idx in short_idx:
            sym = ready_symbols[idx]
            price = closes[sym]
            qty = round(self.config.POSITION_SIZE_USD / price, 0)
            if qty < 1:
                continue
            self.order_manager.short_sell(sym, qty)
            self._current_positions[sym] = (qty, -1, price)
            self.logger.info(f"SHORT {sym} qty={qty} price={price:.2f}")

    def _extract_closes(self, bars) -> dict[str, float]:
        result = {}
        for sym in self.config.SYMBOLS:
            try:
                result[sym] = float(bars[sym][-1].close)
            except (KeyError, IndexError, TypeError):
                pass
        return result
