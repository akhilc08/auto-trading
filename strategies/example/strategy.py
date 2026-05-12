from core.base_strategy import BaseStrategy


class ExampleStrategy(BaseStrategy):
    """
    Skeleton strategy — logs bar closes and quote ticks.
    Copy this folder to start a new strategy.
    """

    def on_bar(self, bars) -> None:
        for symbol in self.config.SYMBOLS:
            if symbol in bars:
                latest = bars[symbol][-1]
                self.logger.info(f"BAR {symbol} open={latest.open} high={latest.high} low={latest.low} close={latest.close} vol={latest.volume}")

    def on_quote(self, quote) -> None:
        self.logger.info(f"QUOTE {quote.symbol} bid={quote.bid_price} ask={quote.ask_price}")
