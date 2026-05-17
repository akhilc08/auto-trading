import math

from core.base_strategy import BaseStrategy
from strategies.regime_switching.signals import Regime, RegimeState, detect_regime, fetch_vix

# Instruments held per detected regime
_ALLOCATIONS: dict[Regime, list[tuple[str, float]]] = {
    Regime.TRENDING:       [("QQQ", 1.0)],
    Regime.MEAN_REVERTING: [("USMV", 1.0)],
    Regime.RISK_OFF:       [("TLT", 0.6), ("GLD", 0.4)],
    Regime.CRISIS:         [],  # all cash
}


class RegimeSwitchingStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._bars_seen: int = 0
        self._current_regime: Regime | None = None
        self._candidate: Regime | None = None
        self._candidate_days: int = 0

    def _latest_close(self, bars, symbol: str) -> float | None:
        try:
            b = bars[symbol]
            return float(b[-1].close) if b else None
        except Exception:
            return None

    def _spy_history(self) -> list[float]:
        try:
            bars = self.client.get_historical_bars(["SPY"], 252)
            return [float(b.close) for b in bars["SPY"]]
        except Exception:
            return []

    def on_bar(self, bars) -> None:
        self._bars_seen += 1
        if self._bars_seen < self.config.MIN_BARS:
            return

        vix, vix3m = fetch_vix()
        spy_hist = self._spy_history()
        state = detect_regime(vix, vix3m, spy_hist, self.config)

        self.logger.info(
            f"VIX={vix:.1f} TS={state.ts_ratio:.3f} "
            f"SPY_vs_MA200={state.spy_vs_ma200:+.1%} 30d={state.spy_30d_ret:+.1%} "
            f"regime={state.regime.value} conf={state.confidence:.2f} "
            f"(current={self._current_regime})"
        )

        if state.regime != self._current_regime:
            if state.regime == self._candidate:
                self._candidate_days += 1
            else:
                self._candidate = state.regime
                self._candidate_days = 1

            if self._candidate_days >= self.config.REGIME_CONFIRM_DAYS:
                self._switch_to(state, bars)
        else:
            self._candidate = None
            self._candidate_days = 0

    def _switch_to(self, state: RegimeState, bars) -> None:
        prev = self._current_regime
        new = state.regime
        self.logger.info(f"Regime switch {prev} → {new.value} (confirmed {self.config.REGIME_CONFIRM_DAYS}d)")

        # Close existing positions in tradeable universe
        try:
            for pos in self.client.trading.get_all_positions():
                if pos.symbol in self.config.TRADEABLE_SYMBOLS:
                    self.order_manager.close_position(pos.symbol)
        except Exception as exc:
            self.logger.error(f"Error closing positions during regime switch: {exc}")

        self._current_regime = new
        self._candidate = None
        self._candidate_days = 0

        for symbol, weight in _ALLOCATIONS.get(new, []):
            price = self._latest_close(bars, symbol)
            if not price or price <= 0:
                self.logger.warning(f"No price for {symbol}, skipping")
                continue
            qty = max(1, math.floor(self.config.POSITION_SIZE_USD * weight / price))
            self.order_manager.buy(symbol, qty)
            self.logger.info(f"  {new.value}: BUY {qty} {symbol} @ ${price:.2f}")
