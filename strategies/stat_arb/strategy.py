import math
from dataclasses import dataclass, field

import numpy as np
from alpaca.data.timeframe import TimeFrame

from core.base_strategy import BaseStrategy
from strategies.stat_arb.pair_selector import is_valid_pair
from strategies.stat_arb.signals import PairPosition, SignalResult, compute_signal
from strategies.stat_arb.spread import KalmanSpread

_ROLLING_WINDOW = 60  # overridden by config.ROLLING_WINDOW if present


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
        self._rolling_window = getattr(config, "ROLLING_WINDOW", _ROLLING_WINDOW)
        self._prev_proxy_close: float | None = None

    def on_bar(self, bars) -> None:
        # Formation, then evaluate/trade on the SAME call. The Flight runs one-shot (on_bar is
        # called exactly once per fire, with no state persisted), so an early return after
        # formation would mean _update — the only path to any order — never runs and the
        # strategy would never trade. In the persistent runner this also works: the first call
        # does formation + _update, subsequent calls do _update.
        if not self._initialized:
            self._run_formation()
            self._restore_state()
        self._update(bars)
        self._persist_state()

    def _restore_state(self) -> None:
        """Overlay position state saved by a prior fire onto the freshly-formed pairs, so the
        one-shot Flight remembers what it holds and can manage exits / avoid re-stacking. A held
        pair that did not re-form this run (e.g. cointegration dropped it) is flattened."""
        if self.state_store is None:
            return
        saved = self.state_store.load()
        by_key = {f"{p.symbol_a}/{p.symbol_b}": p for p in self._pairs}
        for key, st in saved.items():
            pair = by_key.get(key)
            if pair is not None:
                try:
                    pair.position = PairPosition(st.get("position", "none"))
                    pair.bars_held = int(st.get("bars_held", 0))
                    pair.cooldown_bars = int(st.get("cooldown_bars", 0))
                    pair.qty_a = float(st.get("qty_a", 0.0))
                    pair.qty_b = float(st.get("qty_b", 0.0))
                except (ValueError, TypeError):
                    self.logger.error(f"Bad saved state for pair {key}, ignoring")
            elif st.get("position", "none") != "none":
                self._force_exit_orphan(key, st)

    def _persist_state(self) -> None:
        if self.state_store is None:
            return
        state = {}
        for p in self._pairs:
            if p.position is not PairPosition.NONE or p.cooldown_bars > 0:
                state[f"{p.symbol_a}/{p.symbol_b}"] = {
                    "position": p.position.value,
                    "bars_held": p.bars_held,
                    "cooldown_bars": p.cooldown_bars,
                    "qty_a": p.qty_a,
                    "qty_b": p.qty_b,
                }
        self.state_store.save(state)

    def _force_exit_orphan(self, key: str, st: dict) -> None:
        try:
            sym_a, sym_b = key.split("/", 1)
            position = st.get("position", "none")
            qty_a = float(st.get("qty_a", 0.0))
            qty_b = float(st.get("qty_b", 0.0))
        except (ValueError, TypeError):
            return
        self.logger.warning(f"Flattening orphaned pair {key} (no longer in formed book)")
        if position == "long":
            self.order_manager.sell(sym_a, qty_a)
            self.order_manager.buy_to_cover(sym_b, qty_b)
        elif position == "short":
            self.order_manager.buy_to_cover(sym_a, qty_a)
            self.order_manager.sell(sym_b, qty_b)

    def _run_formation(self) -> None:
        self.logger.info("Running formation: fetching historical bars...")
        all_symbols = list({s for pair in self.config.PAIRS for s in pair})
        proxy = getattr(self.config, "MARKET_PROXY", None)
        if proxy and proxy not in all_symbols:
            all_symbols.append(proxy)
        hist = self.client.get_historical_bars(all_symbols, self.config.FORMATION_DAYS)

        log_prices: dict[str, np.ndarray] = {}
        for symbol in all_symbols:
            try:
                bars_list = hist[symbol]
                log_prices[symbol] = np.array([math.log(b.close) for b in bars_list])
            except (KeyError, IndexError):
                self.logger.warning(
                    f"No historical data for {symbol}, skipping pairs involving it"
                )

        for sym_a, sym_b in self.config.PAIRS:
            if sym_a not in log_prices or sym_b not in log_prices:
                continue

            lp_a = log_prices[sym_a]
            lp_b = log_prices[sym_b]
            n = min(len(lp_a), len(lp_b))
            if n < max(60, self._rolling_window):
                self.logger.warning(
                    f"Insufficient history for {sym_a}/{sym_b} ({n} bars), skipping"
                )
                continue

            lp_a, lp_b = lp_a[-n:], lp_b[-n:]

            if not is_valid_pair(
                lp_a,
                lp_b,
                pvalue_threshold=self.config.COINT_PVALUE_THRESHOLD,
                hlife_min=self.config.HLIFE_MIN_DAYS,
                hlife_max=self.config.HLIFE_MAX_DAYS,
            ):
                self.logger.info(
                    f"Pair {sym_a}/{sym_b} failed cointegration screen, skipping"
                )
                continue

            kalman = KalmanSpread(
                delta=self.config.KALMAN_DELTA,
                obs_noise=self.config.KALMAN_OBS_NOISE,
            )
            innov_buf: list[float] = []
            for a, b in zip(lp_a, lp_b):
                e, _ = kalman.update(a, b)
                innov_buf.append(e)
            innov_buf = innov_buf[-self._rolling_window :]

            self._pairs.append(_PairState(sym_a, sym_b, kalman, innov_buf=innov_buf))
            self.logger.info(
                f"Pair {sym_a}/{sym_b} added to book (β={kalman.beta:.4f})"
            )

        if proxy:
            try:
                self._prev_proxy_close = float(hist[proxy][-1].close)
            except (KeyError, IndexError, TypeError):
                self._prev_proxy_close = None

        self.logger.info(f"Formation complete: {len(self._pairs)} active pairs")
        self._initialized = True

    def _update(self, bars) -> None:
        blackout = self._crisis_blackout(bars)

        for pair in self._pairs:
            if pair.cooldown_bars > 0:
                pair.cooldown_bars -= 1

            price_a = self._latest_close(bars, pair.symbol_a)
            price_b = self._latest_close(bars, pair.symbol_b)
            if price_a is None or price_b is None:
                continue

            e, _ = pair.kalman.update(math.log(price_a), math.log(price_b))
            pair.innov_buf.append(e)
            if len(pair.innov_buf) > self._rolling_window:
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

            if signal is SignalResult.ENTER_LONG and pair.cooldown_bars == 0 and not blackout:
                self._enter_long(pair, price_a, price_b)
            elif signal is SignalResult.ENTER_SHORT and pair.cooldown_bars == 0 and not blackout:
                self._enter_short(pair, price_a, price_b)
            elif signal in (
                SignalResult.EXIT,
                SignalResult.STOP,
                SignalResult.TIME_STOP,
            ):
                self._exit_pair(pair, signal)

            if pair.position is not PairPosition.NONE:
                pair.bars_held += 1

    def _crisis_blackout(self, bars) -> bool:
        """Suppress NEW entries on an extreme market-wide daily move (crisis
        regime), when mean-reversion pair relationships are most likely to break.
        Exits/stops are unaffected. Returns False when no proxy or prior close is
        known. Tracks the proxy close across bars to measure the daily move."""
        proxy = getattr(self.config, "MARKET_PROXY", None)
        threshold = getattr(self.config, "VIX_BLACKOUT_DAILY_MOVE", None)
        if proxy is None or threshold is None:
            return False

        price = self._latest_close(bars, proxy)
        if price is None:
            # The scheduler may not include the proxy in its bar fetch; get it directly.
            try:
                proxy_bars = self.client.get_latest_bars([proxy], TimeFrame.Day)
                price = self._latest_close(proxy_bars, proxy)
            except Exception as e:
                self.logger.error(f"Failed to fetch proxy {proxy}: {e}")
                return False
        if price is None or price <= 0:
            return False

        prev = self._prev_proxy_close
        self._prev_proxy_close = price
        if prev is None or prev <= 0:
            return False

        daily_move = abs(price / prev - 1.0)
        if daily_move >= threshold:
            self.logger.info(
                f"Crisis blackout: {proxy} daily move {daily_move:.2%} >= "
                f"{threshold:.2%}; suppressing new entries"
            )
            return True
        return False

    def _enter_long(self, pair: _PairState, price_a: float, price_b: float) -> None:
        qty_a = round(self.config.POSITION_SIZE_USD / price_a, 0)
        qty_b = round(self.config.POSITION_SIZE_USD / price_b, 0)
        if qty_a < 1 or qty_b < 1:
            return
        order_a = self.order_manager.buy(pair.symbol_a, qty_a)
        order_b = self.order_manager.short_sell(pair.symbol_b, qty_b)
        if order_a is None or order_b is None:
            # Don't record a position the broker didn't fully accept; unwind any filled leg.
            if order_a is not None:
                self.order_manager.sell(pair.symbol_a, qty_a)
            if order_b is not None:
                self.order_manager.buy_to_cover(pair.symbol_b, qty_b)
            self.logger.error(f"Entry failed for {pair.symbol_a}/{pair.symbol_b}; staying flat")
            return
        pair.position = PairPosition.LONG
        pair.bars_held = 0
        pair.qty_a = qty_a
        pair.qty_b = qty_b

    def _enter_short(self, pair: _PairState, price_a: float, price_b: float) -> None:
        qty_a = round(self.config.POSITION_SIZE_USD / price_a, 0)
        qty_b = round(self.config.POSITION_SIZE_USD / price_b, 0)
        if qty_a < 1 or qty_b < 1:
            return
        order_a = self.order_manager.short_sell(pair.symbol_a, qty_a)
        order_b = self.order_manager.buy(pair.symbol_b, qty_b)
        if order_a is None or order_b is None:
            if order_a is not None:
                self.order_manager.buy_to_cover(pair.symbol_a, qty_a)
            if order_b is not None:
                self.order_manager.sell(pair.symbol_b, qty_b)
            self.logger.error(f"Entry failed for {pair.symbol_a}/{pair.symbol_b}; staying flat")
            return
        pair.position = PairPosition.SHORT
        pair.bars_held = 0
        pair.qty_a = qty_a
        pair.qty_b = qty_b

    def _exit_pair(self, pair: _PairState, reason: SignalResult) -> None:
        if pair.position is PairPosition.NONE:
            return
        self.logger.info(
            f"Exiting {pair.symbol_a}/{pair.symbol_b} reason={reason.value}"
        )
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
