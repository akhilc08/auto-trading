from dataclasses import dataclass, field

from core.base_strategy import BaseStrategy
from strategies.post_earnings_drift import config
from strategies.post_earnings_drift.signals import get_earnings_surprise


@dataclass
class PEADPosition:
    symbol: str
    direction: str  # "long" or "short"
    qty: float
    days_held: int
    entry_price: float


class PEADStrategy(BaseStrategy):
    def __init__(self, client, order_manager, logger, cfg=None, config=None):
        import strategies.post_earnings_drift.config as _default_cfg
        super().__init__(client, order_manager, logger, cfg or config or _default_cfg)
        self._positions: dict[str, PEADPosition] = {}
        self._reconcile_positions()

    def _reconcile_positions(self) -> None:
        """Register any existing Alpaca positions for our symbols on startup."""
        try:
            existing = self.client.trading.get_all_positions()
        except Exception as e:
            self.logger.error(f"Failed to fetch existing positions: {e}")
            return
        for pos in existing:
            sym = pos.symbol
            if sym not in self.config.SYMBOLS:
                continue
            qty = float(pos.qty)
            direction = "long" if qty > 0 else "short"
            entry = float(pos.avg_entry_price)
            self._positions[sym] = PEADPosition(
                symbol=sym,
                direction=direction,
                qty=abs(qty),
                days_held=15,  # conservative midpoint after restart
                entry_price=entry,
            )
            self.logger.info(
                f"Reconciled existing position: {sym} {direction} qty={abs(qty):.2f} "
                f"entry={entry:.2f} days_held=15"
            )

    @staticmethod
    def _latest_close(bars, symbol: str) -> float | None:
        try:
            return float(bars[symbol][-1].close)
        except (KeyError, IndexError, TypeError):
            return None

    def on_bar(self, bars) -> None:
        # --- Age and exit existing positions ---
        symbols_to_remove = []
        for sym, pos in list(self._positions.items()):
            pos.days_held += 1
            current_price = self._latest_close(bars, sym)
            if current_price is None:
                continue

            direction_sign = 1 if pos.direction == "long" else -1
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price * direction_sign

            if pnl_pct < -self.config.STOP_LOSS_PCT:
                self.logger.info(
                    f"PEAD stop-loss: {sym} {pos.direction} pnl={pnl_pct:.2%} "
                    f"entry={pos.entry_price:.2f} current={current_price:.2f}"
                )
                self.order_manager.close_position(sym)
                symbols_to_remove.append(sym)
                continue

            if pos.days_held >= self.config.HOLDING_DAYS:
                self.logger.info(
                    f"PEAD time-exit: {sym} {pos.direction} days_held={pos.days_held} "
                    f"entry={pos.entry_price:.2f} current={current_price:.2f}"
                )
                self.order_manager.close_position(sym)
                symbols_to_remove.append(sym)
                continue

        for sym in symbols_to_remove:
            del self._positions[sym]

        # --- Scan for new earnings ---
        candidates: list[tuple[str, float]] = []
        for sym in self.config.SYMBOLS:
            if sym in self._positions:
                continue
            surprise = get_earnings_surprise(sym, self.config.LOOKBACK_DAYS)
            if surprise is None:
                continue
            if abs(surprise) >= self.config.SURPRISE_MIN_PCT:
                candidates.append((sym, surprise))

        # Sort by absolute surprise descending to prioritise strongest signals
        candidates.sort(key=lambda x: abs(x[1]), reverse=True)

        # --- Enter up to MAX_NEW_POSITIONS_PER_DAY new trades ---
        new_entries = 0
        for sym, surprise in candidates:
            if new_entries >= self.config.MAX_NEW_POSITIONS_PER_DAY:
                break
            current_price = self._latest_close(bars, sym)
            if current_price is None or current_price <= 0:
                continue

            # Scale position size by surprise strength
            size_usd = self.config.POSITION_SIZE_USD * min(1.0, abs(surprise) / 20.0 + 0.5)
            qty = size_usd / current_price
            qty = round(qty, 2)
            if qty <= 0:
                continue

            if surprise > 0:
                self.order_manager.buy(sym, qty)
                direction = "long"
                self.logger.info(
                    f"PEAD enter long: {sym} surprise={surprise:.1f}% "
                    f"qty={qty:.2f} price={current_price:.2f}"
                )
            else:
                self.order_manager.short_sell(sym, qty)
                direction = "short"
                self.logger.info(
                    f"PEAD enter short: {sym} surprise={surprise:.1f}% "
                    f"qty={qty:.2f} price={current_price:.2f}"
                )

            self._positions[sym] = PEADPosition(
                symbol=sym,
                direction=direction,
                qty=qty,
                days_held=0,
                entry_price=current_price,
            )
            new_entries += 1
