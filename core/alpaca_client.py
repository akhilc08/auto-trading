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
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
        )
        return self.data.get_stock_bars(request)

    def get_stream(self) -> StockDataStream:
        return StockDataStream(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def get_account(self):
        return self.trading.get_account()
