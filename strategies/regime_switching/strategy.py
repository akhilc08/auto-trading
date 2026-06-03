import math

from core.base_strategy import BaseStrategy
from strategies.regime_switching.signals import (
    Regime,
    RegimeState,
    detect_regime,
    fetch_vix,
    fetch_vix_series,
)

# Instruments held per detected regime
_ALLOCATIONS: dict[Regime, list[tuple[str, float]]] = {
    Regime.TRENDING:       [("QQQ", 1.0)],
    Regime.MEAN_REVERTING: [("USMV", 1.0)],
    Regime.RISK_OFF:       [("TLT", 0.6), ("GLD", 0.4)],
    Regime.CRISIS:         [],  # all cash
}

# Every symbol this strategy ever trades. On a shared Alpaca account we can only safely manage
# positions in our own allocation universe; we never touch symbols outside it (e.g. another
# strategy's SPY/IWM/AGG). NOTE: QQQ/TLT still overlap trend_following on the shared account —
# full isolation requires a dedicated account per strategy.
_OWN_UNIVERSE = {sym for alloc in _ALLOCATIONS.values() for sym, _ in alloc}


class RegimeSwitchingStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, config):
        super().__init__(client, order_manager, logger, config)
        self._bars_seen: int = 0
        self._current_regime: Regime | None = None

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
        if vix is None or vix3m is None:
            self.logger.warning("VIX data unavailable, skipping regime check")
            return
        spy_hist = self._spy_history()
        state = detect_regime(vix, vix3m, spy_hist, self.config)

        self.logger.info(
            f"VIX={vix:.1f} TS={state.ts_ratio:.3f} "
            f"SPY_vs_MA200={state.spy_vs_ma200:+.1%} 30d={state.spy_30d_ret:+.1%} "
            f"regime={state.regime.value} conf={state.confidence:.2f} "
            f"(current={self._current_regime})"
        )

        # Only commit to a regime that has held for REGIME_CONFIRM_DAYS — reconstructed from
        # recent VIX history rather than counting consecutive in-process on_bar calls (which the
        # one-shot Flight never accumulates).
        if not self._regime_confirmed(state.regime, spy_hist):
            self.logger.info(
                f"Regime {state.regime.value} not confirmed over "
                f"{self.config.REGIME_CONFIRM_DAYS}d; holding"
            )
            return

        self._apply_regime(state, bars)

    def _regime_confirmed(self, target: Regime, spy_hist: list[float]) -> bool:
        days = self.config.REGIME_CONFIRM_DAYS
        if days <= 1:
            return True
        vix_series, vix3m_series = fetch_vix_series(days)
        if vix_series is None or vix3m_series is None:
            # Can't verify stability → don't switch (avoid whipsawing on incomplete data).
            return False
        # Hold the (slow-moving) SPY trend constant and check the fast VIX term-structure
        # dimension across the last `days` sessions; all must imply the same regime.
        for vix, vix3m in zip(vix_series, vix3m_series):
            if detect_regime(vix, vix3m, spy_hist, self.config).regime != target:
                return False
        return True

    def _apply_regime(self, state: RegimeState, bars) -> None:
        new = state.regime
        target = dict(_ALLOCATIONS.get(new, []))

        try:
            positions = self.client.trading.get_all_positions()
        except Exception as exc:
            self.logger.error(f"Error fetching positions during regime apply: {exc}")
            return
        held = {p.symbol for p in positions if p.symbol in _OWN_UNIVERSE}

        # Idempotent: if we already hold exactly the target allocation, do nothing. Without this
        # the stateless one-shot run would re-close-and-rebuy the same regime every single day.
        if held == set(target):
            self.logger.info(f"Already positioned for regime {new.value}; no change")
            self._current_regime = new
            return

        self.logger.info(
            f"Applying regime {new.value} (target={sorted(target)}, held={sorted(held)})"
        )
        # Close only our own-universe holdings that are not part of the new target.
        for symbol in held - set(target):
            self.order_manager.close_position(symbol)
        # Buy target instruments we are not already holding.
        for symbol, weight in target.items():
            if symbol in held:
                continue
            price = self._latest_close(bars, symbol)
            if not price or price <= 0:
                self.logger.warning(f"No price for {symbol}, skipping")
                continue
            qty = max(1, math.floor(self.config.POSITION_SIZE_USD * weight / price))
            self.order_manager.buy(symbol, qty)
            self.logger.info(f"  {new.value}: BUY {qty} {symbol} @ ${price:.2f}")
        self._current_regime = new
