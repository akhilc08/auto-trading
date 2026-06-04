import math
from dataclasses import dataclass, field

import numpy as np
import statsmodels.api as sm
from alpaca.data.timeframe import TimeFrame

from core.base_strategy import BaseStrategy
from strategies.market_neutral.signals import Position, Signal, compute_signal


@dataclass
class _StockState:
    symbol: str
    beta_hat: float = 0.0
    alpha_hat: float = 0.0
    resid_buf: list = field(default_factory=list)
    position: Position = Position.NONE
    bars_held: int = 0
    cooldown_bars: int = 0
    qty_stock: float = 0.0
    qty_market: float = 0.0


class MarketNeutralStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._initialized = False
        self._stocks: list[_StockState] = []

    def on_bar(self, bars) -> None:
        if not self._initialized:
            self._run_formation()
            self._restore_state()
        self._update(bars)
        self._persist_state()

    def _restore_state(self) -> None:
        """Overlay position state saved by a prior fire onto the freshly-formed stocks, so the
        one-shot Flight remembers what it holds and can manage exits / avoid re-stacking. A held
        stock that did not re-form this run is flattened."""
        if self.state_store is None:
            return
        saved = self.state_store.load()
        by_sym = {s.symbol: s for s in self._stocks}
        for sym, st in saved.items():
            stock = by_sym.get(sym)
            if stock is not None:
                try:
                    stock.position = Position(st.get("position", "none"))
                    stock.bars_held = int(st.get("bars_held", 0))
                    stock.cooldown_bars = int(st.get("cooldown_bars", 0))
                    stock.qty_stock = float(st.get("qty_stock", 0.0))
                    stock.qty_market = float(st.get("qty_market", 0.0))
                except (ValueError, TypeError):
                    self.logger.error(f"Bad saved state for {sym}, ignoring")
            elif st.get("position", "none") != "none":
                self._force_exit_orphan(sym, st)

    def _persist_state(self) -> None:
        if self.state_store is None:
            return
        state = {}
        for s in self._stocks:
            if s.position is not Position.NONE or s.cooldown_bars > 0:
                state[s.symbol] = {
                    "position": s.position.value,
                    "bars_held": s.bars_held,
                    "cooldown_bars": s.cooldown_bars,
                    "qty_stock": s.qty_stock,
                    "qty_market": s.qty_market,
                }
        self.state_store.save(state)

    def _force_exit_orphan(self, sym: str, st: dict) -> None:
        try:
            position = st.get("position", "none")
            qty_stock = float(st.get("qty_stock", 0.0))
            qty_market = float(st.get("qty_market", 0.0))
        except (ValueError, TypeError):
            return
        self.logger.warning(f"Flattening orphaned position {sym} (no longer in formed book)")
        proxy = self.config.MARKET_PROXY
        if position == "long":
            self.order_manager.sell(sym, qty_stock)
            self.order_manager.buy_to_cover(proxy, qty_market)
        elif position == "short":
            self.order_manager.buy_to_cover(sym, qty_stock)
            self.order_manager.sell(proxy, qty_market)

    def _run_formation(self) -> None:
        self.logger.info("Running formation: fetching historical bars...")
        all_symbols = list(self.config.SYMBOLS) + [self.config.MARKET_PROXY]
        hist = self.client.get_historical_bars(all_symbols, self.config.FORMATION_DAYS)

        try:
            market_bars = hist[self.config.MARKET_PROXY]
            log_market = np.array([math.log(b.close) for b in market_bars])
        except (KeyError, IndexError):
            self.logger.warning(f"No historical data for {self.config.MARKET_PROXY}, aborting formation")
            self._initialized = True
            return

        for symbol in self.config.SYMBOLS:
            try:
                stock_bars = hist[symbol]
                log_stock = np.array([math.log(b.close) for b in stock_bars])
            except (KeyError, IndexError):
                self.logger.warning(f"No historical data for {symbol}, skipping")
                continue

            n = min(len(log_stock), len(log_market))
            if n < 60:
                self.logger.warning(f"Insufficient history for {symbol} ({n} bars), skipping")
                continue

            ls = log_stock[-n:]
            lm = log_market[-n:]

            X = sm.add_constant(lm)
            ols_result = sm.OLS(ls, X).fit()
            beta_hat = float(ols_result.params[1])
            alpha_hat = float(ols_result.params[0])

            residuals = ls - beta_hat * lm - alpha_hat
            resid_buf = list(residuals[-self.config.ROLLING_WINDOW:])

            state = _StockState(symbol=symbol, beta_hat=beta_hat, alpha_hat=alpha_hat, resid_buf=resid_buf)
            self._stocks.append(state)
            self.logger.info(f"{symbol} added: beta_hat={beta_hat:.4f}")

        self.logger.info(f"Formation complete: {len(self._stocks)} active stocks")
        self._initialized = True

    def _update(self, bars) -> None:
        market_price = self._latest_close(bars, self.config.MARKET_PROXY)
        if market_price is None:
            # The scheduler only fetches config.SYMBOLS, which excludes
            # MARKET_PROXY, so fetch the proxy's latest close ourselves.
            market_price = self._fetch_proxy_price()
        if market_price is None:
            self.logger.warning(f"No price for {self.config.MARKET_PROXY}, skipping bar")
            return
        log_market_now = math.log(market_price)

        for stock in self._stocks:
            if stock.cooldown_bars > 0:
                stock.cooldown_bars -= 1

            stock_price = self._latest_close(bars, stock.symbol)
            if stock_price is None:
                continue
            log_stock_now = math.log(stock_price)

            residual = log_stock_now - stock.beta_hat * log_market_now - stock.alpha_hat
            stock.resid_buf.append(residual)
            if len(stock.resid_buf) > self.config.ROLLING_WINDOW:
                stock.resid_buf.pop(0)

            rbuf = np.array(stock.resid_buf)
            rbuf_std = float(rbuf.std())
            zscore = (residual - float(rbuf.mean())) / rbuf_std if rbuf_std > 1e-10 else 0.0

            signal = compute_signal(
                zscore=zscore,
                position=stock.position,
                bars_held=stock.bars_held,
                entry_zscore=self.config.ENTRY_ZSCORE,
                exit_zscore=self.config.EXIT_ZSCORE,
                stoploss_zscore=self.config.STOPLOSS_ZSCORE,
                max_holding_days=self.config.MAX_HOLDING_DAYS,
            )

            self.logger.info(
                f"{stock.symbol} z={zscore:.3f} pos={stock.position.value} signal={signal.value}"
            )

            if signal is Signal.ENTER_LONG and stock.cooldown_bars == 0:
                self._enter_long(stock, stock_price, market_price)
            elif signal is Signal.ENTER_SHORT and stock.cooldown_bars == 0:
                self._enter_short(stock, stock_price, market_price)
            elif signal in (Signal.EXIT, Signal.STOP, Signal.TIME_STOP):
                self._exit_stock(stock, signal)

            if stock.position is not Position.NONE:
                stock.bars_held += 1

    def _enter_long(self, stock: _StockState, stock_price: float, market_price: float) -> None:
        qty_stock = round(self.config.POSITION_SIZE_USD / stock_price, 0)
        qty_market = round(self.config.POSITION_SIZE_USD * stock.beta_hat / market_price, 0)
        if qty_stock < 1 or qty_market < 1:
            return
        order_s = self.order_manager.buy(stock.symbol, qty_stock)
        order_m = self.order_manager.short_sell(self.config.MARKET_PROXY, qty_market)
        if order_s is None or order_m is None:
            # Don't record a position the broker didn't fully accept; unwind any filled leg.
            if order_s is not None:
                self.order_manager.sell(stock.symbol, qty_stock)
            if order_m is not None:
                self.order_manager.buy_to_cover(self.config.MARKET_PROXY, qty_market)
            self.logger.error(f"Entry failed for {stock.symbol}; staying flat")
            return
        stock.position = Position.LONG
        stock.bars_held = 0
        stock.qty_stock = qty_stock
        stock.qty_market = qty_market

    def _enter_short(self, stock: _StockState, stock_price: float, market_price: float) -> None:
        qty_stock = round(self.config.POSITION_SIZE_USD / stock_price, 0)
        qty_market = round(self.config.POSITION_SIZE_USD * stock.beta_hat / market_price, 0)
        if qty_stock < 1 or qty_market < 1:
            return
        order_s = self.order_manager.short_sell(stock.symbol, qty_stock)
        order_m = self.order_manager.buy(self.config.MARKET_PROXY, qty_market)
        if order_s is None or order_m is None:
            if order_s is not None:
                self.order_manager.buy_to_cover(stock.symbol, qty_stock)
            if order_m is not None:
                self.order_manager.sell(self.config.MARKET_PROXY, qty_market)
            self.logger.error(f"Entry failed for {stock.symbol}; staying flat")
            return
        stock.position = Position.SHORT
        stock.bars_held = 0
        stock.qty_stock = qty_stock
        stock.qty_market = qty_market

    def _exit_stock(self, stock: _StockState, reason: Signal) -> None:
        if stock.position is Position.NONE:
            return
        self.logger.info(f"Exiting {stock.symbol} reason={reason.value}")
        if stock.position is Position.LONG:
            self.order_manager.sell(stock.symbol, stock.qty_stock)
            self.order_manager.buy_to_cover(self.config.MARKET_PROXY, stock.qty_market)
        else:
            self.order_manager.buy_to_cover(stock.symbol, stock.qty_stock)
            self.order_manager.sell(self.config.MARKET_PROXY, stock.qty_market)
        stock.position = Position.NONE
        stock.bars_held = 0
        stock.qty_stock = 0.0
        stock.qty_market = 0.0
        if reason is Signal.STOP:
            stock.cooldown_bars = self.config.REENTRY_COOLDOWN_DAYS

    def _fetch_proxy_price(self) -> float | None:
        try:
            proxy_bars = self.client.get_latest_bars([self.config.MARKET_PROXY], TimeFrame.Day)
            return self._latest_close(proxy_bars, self.config.MARKET_PROXY)
        except Exception as e:
            self.logger.error(f"Failed to fetch {self.config.MARKET_PROXY} price: {e}")
            return None

    @staticmethod
    def _latest_close(bars, symbol: str) -> float | None:
        try:
            return float(bars[symbol][-1].close)
        except (KeyError, IndexError, TypeError):
            return None
