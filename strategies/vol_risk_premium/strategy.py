import math

from alpaca.data.timeframe import TimeFrame

from core.base_strategy import BaseStrategy
from strategies.vol_risk_premium import config
from strategies.vol_risk_premium.signals import Signal, compute_signal, fetch_vix, realized_vol


class VRPStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, cfg=None, config=None):
        import strategies.vol_risk_premium.config as _default_cfg
        super().__init__(client, order_manager, logger, cfg or config or _default_cfg)
        self._spy_returns: list[float] = []
        self._prev_spy: float = 0.0
        self._bars_seen: int = 0
        self._preload_history()

    def _preload_history(self) -> None:
        try:
            bars = self.client.get_historical_bars(["SPY"], 30, TimeFrame.Day)
            spy_bars = bars["SPY"]
            closes = [float(b.close) for b in spy_bars]
            if len(closes) < 2:
                return
            for i in range(1, len(closes)):
                if closes[i - 1] > 1e-10:
                    self._spy_returns.append(math.log(closes[i] / closes[i - 1]))
            self._prev_spy = closes[-1]
            self._bars_seen = len(self._spy_returns)
        except Exception:
            pass

    @staticmethod
    def _latest_close(bars, symbol: str) -> float | None:
        try:
            return float(bars[symbol][-1].close)
        except Exception:
            return None

    def on_bar(self, bars) -> None:
        spy_price = self._latest_close(bars, "SPY")
        svxy_price = self._latest_close(bars, config.INSTRUMENT)

        if spy_price is not None and self._prev_spy > 1e-10:
            self._spy_returns.append(math.log(spy_price / self._prev_spy))
            if len(self._spy_returns) > 22:
                self._spy_returns = self._spy_returns[-22:]
        if spy_price is not None:
            self._prev_spy = spy_price

        self._bars_seen += 1

        if self._bars_seen < config.MIN_BARS:
            self.logger.info(f"Warming up: {self._bars_seen}/{config.MIN_BARS} bars seen")
            return

        if svxy_price is None:
            self.logger.info("SVXY price unavailable, skipping bar")
            return

        vix, vix3m = fetch_vix()
        if vix is None or vix3m is None:
            self.logger.warning("VIX data unavailable, skipping bar")
            return
        rv = realized_vol(self._spy_returns[-22:])
        signal, composite = compute_signal(
            vix=vix,
            vix3m=vix3m,
            rv=rv,
            vix_crisis=config.VIX_CRISIS,
            vix_caution=config.VIX_CAUTION,
            composite_entry=config.COMPOSITE_ENTRY,
            composite_full=config.COMPOSITE_FULL,
        )

        vrp_spread_bp = int(((vix / 100.0) - rv) * 10000)
        ts_ratio = vix3m / vix if vix > 1e-10 else 1.0
        self.logger.info(
            f"VIX={vix:.2f} VIX3M={vix3m:.2f} RV={rv*100:.2f}% "
            f"VRP={vrp_spread_bp}bp TS={ts_ratio:.4f} score={composite:.4f} signal={signal.value}"
        )

        position = self.order_manager.get_position(config.INSTRUMENT)

        if signal == Signal.STRONG and position is None:
            qty = max(1, math.floor(config.POSITION_SIZE_USD / svxy_price))
            self.order_manager.buy(config.INSTRUMENT, qty)
        elif signal == Signal.MODERATE and position is None:
            qty = max(1, math.floor((config.POSITION_SIZE_USD * 0.5) / svxy_price))
            self.order_manager.buy(config.INSTRUMENT, qty)
        elif signal == Signal.NONE and position is not None:
            self.order_manager.close_position(config.INSTRUMENT)
