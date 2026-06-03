import os
import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


class AlpacaClient:
    def __init__(self, mode: str = "paper"):
        self.api_key = os.environ["ALPACA_API_KEY"]
        self.secret_key = os.environ["ALPACA_SECRET_KEY"]
        self.paper = mode == "paper"

        self.trading = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )
        self.data = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def get_latest_bars(self, symbols: list[str], timeframe: TimeFrame = TimeFrame.Minute):
        if timeframe == TimeFrame.Day:
            lookback = datetime.timedelta(days=5)
        elif timeframe == TimeFrame.Hour:
            lookback = datetime.timedelta(hours=2)
        else:
            lookback = datetime.timedelta(minutes=10)
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=datetime.datetime.now(datetime.timezone.utc) - lookback,
        )
        # Return the plain {symbol: [Bar, ...]} dict so consumers can use both
        # `symbol in bars` and `bars[symbol]` (a raw BarSet supports neither).
        return self.data.get_stock_bars(request).data

    def get_historical_bars(
        self,
        symbols: list[str],
        n_days: int,
        timeframe: TimeFrame = TimeFrame.Day,
    ):
        # multiply by 1.5 to convert trading days to calendar days (accounts for weekends + holidays)
        calendar_days = int(n_days * 1.5) + 14
        start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=calendar_days)
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=start,
        )
        return self.data.get_stock_bars(request).data

    def get_stream(self) -> StockDataStream:
        return StockDataStream(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def get_account(self):
        return self.trading.get_account()
