from abc import ABC


class BaseStrategy(ABC):
    def __init__(self, client, order_manager, logger, config):
        self.client = client
        self.order_manager = order_manager
        self.logger = logger
        self.config = config

    def on_bar(self, bars) -> None:
        """Override for cron-based strategies. Called with latest bars dict."""
        pass

    def on_quote(self, quote) -> None:
        """Override for streaming strategies. Called on each quote tick."""
        pass
