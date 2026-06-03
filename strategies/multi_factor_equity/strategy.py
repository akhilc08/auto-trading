from collections import deque

import numpy as np

from core.base_strategy import BaseStrategy
from strategies.multi_factor_equity.signals import composite_score, select_legs


class MultiFactorStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._initialized = False
        self._hist_dates: list = []
        self._max_buf = max(config.MOM_LOOKBACK, config.VOL_LOOKBACK) + 10
        self._return_history: dict[str, deque] = {
            sym: deque(maxlen=self._max_buf) for sym in config.SYMBOLS
        }
        self._prev_close: dict[str, float] = {}
        self._current_positions: dict[str, tuple[float, int, float]] = {}

    def on_bar(self, bars) -> None:
        if not self._initialized:
            self._seed_history()
            self._initialized = True

        closes = self._extract_closes(bars)
        if not closes:
            return

        for sym, price in closes.items():
            if sym in self._prev_close and self._prev_close[sym] > 0:
                log_ret = np.log(price / self._prev_close[sym])
                self._return_history[sym].append(log_ret)
            self._prev_close[sym] = price

        if not self._is_rebalance_day(self._latest_bar_date(bars)):
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

    def _seed_history(self) -> None:
        """Preload rolling return history from historical bars so the strategy is
        ready on day one. Without this it must accumulate ~MOM_LOOKBACK live daily
        bars (one per day) before it can rebalance — a window that never completes
        because process restarts reset the in-memory deques."""
        n_days = (
            max(self.config.MOM_LOOKBACK, self.config.VOL_LOOKBACK)
            + self.config.REV_LOOKBACK + 10
        )
        try:
            hist = self.client.get_historical_bars(self.config.SYMBOLS, n_days)
        except Exception as e:
            self.logger.error(f"Failed to preload history: {e}")
            return
        # Capture the recent trading-day calendar (from any available symbol) so the rebalance
        # cadence can be derived from dates instead of an in-process counter that never
        # accumulates across one-shot Flight runs.
        for sym in self.config.SYMBOLS:
            try:
                self._hist_dates = [b.timestamp.date() for b in hist[sym]]
                break
            except (KeyError, IndexError, TypeError, AttributeError):
                continue
        seeded = 0
        for sym in self.config.SYMBOLS:
            try:
                closes = [float(b.close) for b in hist[sym]]
            except (KeyError, IndexError, TypeError):
                continue
            for i in range(1, len(closes)):
                if closes[i - 1] > 0:
                    self._return_history[sym].append(np.log(closes[i] / closes[i - 1]))
            if closes:
                self._prev_close[sym] = closes[-1]
                seeded += 1
        self.logger.info(
            f"Preloaded return history for {seeded}/{len(self.config.SYMBOLS)} symbols"
        )

    def _extract_closes(self, bars) -> dict[str, float]:
        result = {}
        for sym in self.config.SYMBOLS:
            try:
                result[sym] = float(bars[sym][-1].close)
            except (KeyError, IndexError, TypeError):
                pass
        return result

    def _latest_bar_date(self, bars):
        for sym in self.config.SYMBOLS:
            try:
                return bars[sym][-1].timestamp.date()
            except (KeyError, IndexError, TypeError, AttributeError):
                continue
        return None

    def _is_rebalance_day(self, today) -> bool:
        """Rebalance on the first trading day of each calendar month (≈ the original
        REBALANCE_FREQ≈21 monthly cadence), derived from the trading-day calendar instead of an
        in-process counter — the one-shot Flight re-runs __init__ every fire, so a counter never
        accumulates. Today is the first trading day of its month when no earlier trading day in
        the same month appears in the recent history. Defaults to True when the date can't be
        determined so this gate never silently blocks all trading."""
        if today is None:
            return True
        for d in self._hist_dates:
            if d < today and d.year == today.year and d.month == today.month:
                return False
        return True
