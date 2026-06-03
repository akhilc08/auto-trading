import math

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


class OrderManager:
    def __init__(self, client, logger, md_logger=None, strategy_name="", account_name=""):
        self.client = client
        self.logger = logger
        self.md_logger = md_logger
        self.strategy_name = strategy_name
        self.account_name = account_name

    def _valid_qty(self, side: str, symbol: str, qty: float) -> bool:
        # Reject non-positive / non-finite qty before hitting Alpaca. NaN passes a bare `qty < 1`
        # guard (nan < 1 is False), so check explicitly here and log the rejection rather than
        # letting it surface as a swallowed server-side error that looks like "no trade today".
        if qty is None or not math.isfinite(qty) or qty <= 0:
            self.logger.error(f"{side} rejected: invalid qty={qty} {symbol}")
            return False
        return True

    def get_position(self, symbol: str):
        try:
            return self.client.trading.get_open_position(symbol)
        except Exception:
            return None

    def buy(self, symbol: str, qty: float):
        if not self._valid_qty("BUY", symbol, qty):
            return None
        try:
            self.logger.info(f"BUY {qty} {symbol}")
            order = self.client.trading.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            )
            self.logger.info(f"BUY submitted order_id={order.id}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"BUY failed {symbol}: {e}")
            return None

    def sell(self, symbol: str, qty: float):
        if not self._valid_qty("SELL", symbol, qty):
            return None
        try:
            self.logger.info(f"SELL {qty} {symbol}")
            order = self.client.trading.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            )
            self.logger.info(f"SELL submitted order_id={order.id}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"SELL failed {symbol}: {e}")
            return None

    def short_sell(self, symbol: str, qty: float):
        if not self._valid_qty("SHORT", symbol, qty):
            return None
        try:
            self.logger.info(f"SHORT {qty} {symbol}")
            order = self.client.trading.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            )
            self.logger.info(f"SHORT submitted order_id={order.id}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"SHORT failed {symbol}: {e}")
            return None

    def buy_to_cover(self, symbol: str, qty: float):
        if not self._valid_qty("COVER", symbol, qty):
            return None
        try:
            self.logger.info(f"COVER {qty} {symbol}")
            order = self.client.trading.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            )
            self.logger.info(f"COVER submitted order_id={order.id}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"COVER failed {symbol}: {e}")
            return None

    def close_position(self, symbol: str):
        try:
            self.logger.info(f"Closing position {symbol}")
            order = self.client.trading.close_position(symbol)
            self.logger.info(f"Position closed {symbol}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"Close position failed {symbol}: {e}")
            return None

    def cancel_all_orders(self):
        try:
            self.client.trading.cancel_orders()
            self.logger.info("All orders cancelled")
        except Exception as e:
            self.logger.error(f"Cancel all orders failed: {e}")
