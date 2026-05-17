import math
from dataclasses import dataclass, field

import numpy as np

from core.base_strategy import BaseStrategy
from strategies.stat_arb.pair_selector import cointegration_test, is_valid_pair
from strategies.stat_arb.signals import PairPosition, SignalResult, compute_signal
from strategies.stat_arb.spread import KalmanSpread


_ROLLING_WINDOW = 60


@dataclass
class _PairState:
    symbol_a: str
    symbol_b: str
    kalman: KalmanSpread
    innov_buf: list = field(default_factory=list)
    position: PairPosition = PairPosition.NONE
    bars_held: int = 0
    cooldown_bars: int = 0
    qty_a: float = 0.0
    qty_b: float = 0.0


class StatArbStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._initialized = False
        self._pairs: list[_PairState] = []

    def on_bar(self, bars) -> None:
        if not self._initialized:
            self._run_formation()
        self._update(bars)

    def _run_formation(self) -> None:
        self.logger.info("Running formation: fetching historical bars...")
        all_symbols = list({s for pair in self.config.PAIRS for s in pair})
        hist = self.client.get_historical_bars(all_symbols, self.config.FORMATION_DAYS)

        log_prices: dict[str, np.ndarray] = {}
        for symbol in all_symbols:
            try:
                bars_list = hist[symbol]
                log_prices[symbol] = np.array([math.log(b.close) for b in bars_list])
            except (KeyError, IndexError):
                self.logger.warning(f"No historical data for {symbol}, skipping pairs involving it")

        for sym_a, sym_b in self.config.PAIRS:
            if sym_a not in log_prices or sym_b not in log_prices:
                continue

            lp_a = log_prices[sym_a]
            lp_b = log_prices[sym_b]
            n = min(len(lp_a), len(lp_b))
            if n < 60:
                self.logger.warning(f"Insufficient history for {sym_a}/{sym_b} ({n} bars), skipping")
                continue

            lp_a, lp_b = lp_a[-n:], lp_b[-n:]

            if not is_valid_pair(
                lp_a, lp_b,
                pvalue_threshold=self.config.COINT_PVALUE_THRESHOLD,
                hlife_min=self.config.HLIFE_MIN_DAYS,
                hlife_max=self.config.HLIFE_MAX_DAYS,
            ):
                self.logger.info(f"Pair {sym_a}/{sym_b} failed cointegration screen, skipping")
                continue

            kalman = KalmanSpread(
                delta=self.config.KALMAN_DELTA,
                obs_noise=self.config.KALMAN_OBS_NOISE,
            )
            innov_buf: list[float] = []
            for a, b in zip(lp_a, lp_b):
                e, _ = kalman.update(a, b)
                innov_buf.append(e)
            innov_buf = innov_buf[-_ROLLING_WINDOW:]

            self._pairs.append(_PairState(sym_a, sym_b, kalman, innov_buf=innov_buf))
            self.logger.info(f"Pair {sym_a}/{sym_b} added to book (β={kalman.beta:.4f})")

        self.logger.info(f"Formation complete: {len(self._pairs)} active pairs")
        self._initialized = True

    def _update(self, bars) -> None:
        for pair in self._pairs:
            if pair.cooldown_bars > 0:
                pair.cooldown_bars -= 1

            price_a = self._latest_close(bars, pair.symbol_a)
            price_b = self._latest_close(bars, pair.symbol_b)
            if price_a is None or price_b is None:
                continue

            e, _ = pair.kalman.update(math.log(price_a), math.log(price_b))
            pair.innov_buf.append(e)
            if len(pair.innov_buf) > _ROLLING_WINDOW:
                pair.innov_buf.pop(0)
            ibuf = np.array(pair.innov_buf)
            ibuf_std = float(ibuf.std())
            zscore = (e - float(ibuf.mean())) / ibuf_std if ibuf_std > 1e-10 else 0.0

            signal = compute_signal(
                zscore=zscore,
                position=pair.position,
                bars_held=pair.bars_held,
                entry_zscore=self.config.ENTRY_ZSCORE,
                exit_zscore=self.config.EXIT_ZSCORE,
                stoploss_zscore=self.config.STOPLOSS_ZSCORE,
                max_holding_days=self.config.MAX_HOLDING_DAYS,
            )

            self.logger.info(
                f"{pair.symbol_a}/{pair.symbol_b} z={zscore:.3f} pos={pair.position.value} signal={signal.value}"
            )

            if signal is SignalResult.ENTER_LONG and pair.cooldown_bars == 0:
                self._enter_long(pair, price_a, price_b)
            elif signal is SignalResult.ENTER_SHORT and pair.cooldown_bars == 0:
                self._enter_short(pair, price_a, price_b)
            elif signal in (SignalResult.EXIT, SignalResult.STOP, SignalResult.TIME_STOP):
                self._exit_pair(pair, signal)

            if pair.position is not PairPosition.NONE:
                pair.bars_held += 1

    def _enter_long(self, pair: _PairState, price_a: float, price_b: float) -> None:
        qty_a = round(self.config.POSITION_SIZE_USD / price_a, 0)
        qty_b = round(self.config.POSITION_SIZE_USD / price_b, 0)
        if qty_a < 1 or qty_b < 1:
            return
        self.order_manager.buy(pair.symbol_a, qty_a)
        self.order_manager.short_sell(pair.symbol_b, qty_b)
        pair.position = PairPosition.LONG
        pair.bars_held = 0
        pair.qty_a = qty_a
        pair.qty_b = qty_b

    def _enter_short(self, pair: _PairState, price_a: float, price_b: float) -> None:
        qty_a = round(self.config.POSITION_SIZE_USD / price_a, 0)
        qty_b = round(self.config.POSITION_SIZE_USD / price_b, 0)
        if qty_a < 1 or qty_b < 1:
            return
        self.order_manager.short_sell(pair.symbol_a, qty_a)
        self.order_manager.buy(pair.symbol_b, qty_b)
        pair.position = PairPosition.SHORT
        pair.bars_held = 0
        pair.qty_a = qty_a
        pair.qty_b = qty_b

    def _exit_pair(self, pair: _PairState, reason: SignalResult) -> None:
        if pair.position is PairPosition.NONE:
            return
        self.logger.info(f"Exiting {pair.symbol_a}/{pair.symbol_b} reason={reason.value}")
        if pair.position is PairPosition.LONG:
            self.order_manager.sell(pair.symbol_a, pair.qty_a)
            self.order_manager.buy_to_cover(pair.symbol_b, pair.qty_b)
        else:
            self.order_manager.buy_to_cover(pair.symbol_a, pair.qty_a)
            self.order_manager.sell(pair.symbol_b, pair.qty_b)
        pair.position = PairPosition.NONE
        pair.bars_held = 0
        pair.qty_a = 0.0
        pair.qty_b = 0.0
        if reason is SignalResult.STOP:
            pair.cooldown_bars = self.config.REENTRY_COOLDOWN_DAYS

    @staticmethod
    def _latest_close(bars, symbol: str) -> float | None:
        try:
            return float(bars[symbol][-1].close)
        except (KeyError, IndexError, TypeError):
            return None
