import os
import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
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

    def get_latest_bars(self, symbols: list[str], timeframe: TimeFrame = TimeFrame.Minute, feed=None):
        # Wide enough to clear holidays / long weekends; the latest-bar fallback below covers any
        # larger gap (e.g. the feed's most recent bar predates the lookback).
        if timeframe == TimeFrame.Day:
            lookback = datetime.timedelta(days=15)
        elif timeframe == TimeFrame.Hour:
            lookback = datetime.timedelta(hours=12)
        else:
            lookback = datetime.timedelta(minutes=30)
        kwargs = dict(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=datetime.datetime.now(datetime.timezone.utc) - lookback,
        )
        if feed is not None:
            kwargs["feed"] = feed
        # Plain {symbol: [Bar, ...]} dict so consumers can use both `symbol in bars`
        # and `bars[symbol]` (a raw BarSet supports neither).
        data = self.data.get_stock_bars(StockBarsRequest(**kwargs)).data
        # Any symbol with no bar in the window (holiday gap, or a feed whose latest bar is older
        # than the lookback) falls back to the latest-available-bar endpoint, which is not
        # anchored to a client-clock window and so returns the freshest bar regardless of skew.
        missing = [s for s in symbols if not data.get(s)]
        if missing:
            for sym, bar in self._latest_bar_fallback(missing, feed).items():
                data[sym] = [bar]
        return data

    def _latest_bar_fallback(self, symbols: list[str], feed=None) -> dict:
        kwargs = {"symbol_or_symbols": symbols}
        if feed is not None:
            kwargs["feed"] = feed
        try:
            latest = self.data.get_stock_latest_bar(StockLatestBarRequest(**kwargs))
        except Exception:
            return {}
        return {sym: bar for sym, bar in latest.items() if bar is not None}

    def get_historical_bars(
        self,
        symbols: list[str],
        n_days: int,
        timeframe: TimeFrame = TimeFrame.Day,
        feed=None,
    ):
        # multiply by 1.5 to convert trading days to calendar days (accounts for weekends + holidays)
        calendar_days = int(n_days * 1.5) + 14
        start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=calendar_days)
        kwargs = dict(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=start,
        )
        if feed is not None:
            kwargs["feed"] = feed
        return self.data.get_stock_bars(StockBarsRequest(**kwargs)).data

    def get_stream(self) -> StockDataStream:
        return StockDataStream(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def get_account(self):
        return self.trading.get_account()
