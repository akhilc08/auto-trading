"""Reusable execution-Flight scaffold.

`run_account_flight(account_name, strategy_names, secret_name)` runs one trading account's
strategies on MotherDuck compute:
  1. connect to MotherDuck (duckdb.connect("md:"))
  2. read the account's Alpaca api_key/secret_key from the named MotherDuck secret (plan 02-01)
  3. build a paper Alpaca client from those keys (reuses core.AlpacaClient via env injection)
  4. market-hours guard: get_clock().is_open — exit with no orders when closed (EXEC-07)
  5. for each strategy: discover the BaseStrategy subclass, wire an OrderManager whose order
     methods log to the FlightLogger, fetch latest bars, call on_bar() once
  6. poll Alpaca for fills and update trade rows, then snapshot positions + portfolio

Reused by every execution Flight (exec_stat_arb, exec_macro_vol, exec_trend_following).
Credentials are read only from the secret store and never logged.
"""
import datetime as dt
import importlib
import logging
import os
import re
import traceback

import duckdb
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

from core.alpaca_client import AlpacaClient
from core.base_strategy import BaseStrategy
from core.order_manager import OrderManager

from flights.exec._logger import FlightLogger

logger = logging.getLogger("exec_flight")
logging.basicConfig(level=logging.INFO)


class _IEXAlpacaClient(AlpacaClient):
    """AlpacaClient that fetches bars from the free IEX feed instead of the default SIP feed.

    Alpaca paper accounts without a SIP data subscription get
    "403 — subscription does not permit querying recent SIP data" on bar requests. The IEX feed
    is available on the free tier. Overrides both bar methods so every data call a strategy makes
    through `client` uses IEX. core/ is intentionally left unchanged (plan 02-02 constraint).
    """

    def get_latest_bars(self, symbols, timeframe=TimeFrame.Minute):
        if timeframe == TimeFrame.Day:
            lookback = dt.timedelta(days=5)
        elif timeframe == TimeFrame.Hour:
            lookback = dt.timedelta(hours=2)
        else:
            lookback = dt.timedelta(minutes=10)
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=dt.datetime.now(dt.timezone.utc) - lookback,
            feed=DataFeed.IEX,
        )
        return self.data.get_stock_bars(request).data

    def get_historical_bars(self, symbols, n_days, timeframe=TimeFrame.Day):
        calendar_days = int(n_days * 1.5) + 14
        start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=calendar_days)
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=start,
            feed=DataFeed.IEX,
        )
        return self.data.get_stock_bars(request).data


def _read_alpaca_secret(con, secret_name: str):
    """Read api_key/secret_key from the named MotherDuck secret (plan 02-01 mechanism).

    Credentials are stored as EXTRA_HTTP_HEADERS entries on a TYPE http secret; they read back
    in plaintext via duckdb_secrets().secret_string even with redaction on. Values are split on
    the first '=' so credential values containing '=' survive.
    """
    rows = con.execute(
        "SELECT secret_string FROM duckdb_secrets() WHERE name = ?", [secret_name]
    ).fetchall()
    if not rows:
        raise RuntimeError(f"secret {secret_name!r} not found in MotherDuck")
    match = re.search(r"extra_http_headers=\{(.*)\}", rows[0][0])
    if not match:
        raise RuntimeError(f"secret {secret_name!r} has no extra_http_headers")
    headers = {}
    for token in match.group(1).split(", "):
        if "=" in token:
            key, value = token.split("=", 1)
            headers[key.strip()] = value
    api_key, secret_key = headers.get("api_key"), headers.get("secret_key")
    if not api_key or not secret_key:
        raise RuntimeError(f"secret {secret_name!r} missing api_key/secret_key")
    return api_key, secret_key


def _build_client(api_key: str, secret_key: str) -> AlpacaClient:
    """Reuse core.AlpacaClient (which reads keys from env) by injecting the secret's keys.

    Keeps the exact get_latest_bars / TradingClient construction the strategies rely on, instead
    of reimplementing it. Keys live only in-process; they are removed from the environment after
    the client captures them.
    """
    os.environ["ALPACA_API_KEY"] = api_key
    os.environ["ALPACA_SECRET_KEY"] = secret_key
    try:
        client = _IEXAlpacaClient(mode="paper")
    finally:
        os.environ.pop("ALPACA_API_KEY", None)
        os.environ.pop("ALPACA_SECRET_KEY", None)
    return client


def _discover_strategy_class(strategy_module):
    for attr in dir(strategy_module):
        obj = getattr(strategy_module, attr)
        if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
            return obj
    return None


def run_account_flight(account_name: str, strategy_names: list[str], secret_name: str) -> None:
    con = duckdb.connect("md:")
    api_key, secret_key = _read_alpaca_secret(con, secret_name)
    client = _build_client(api_key, secret_key)

    # Market-hours guard (EXEC-07): exit before instantiating strategies when the market is closed.
    if not client.trading.get_clock().is_open:
        logger.info("market closed — exiting, no orders")
        return

    md = FlightLogger(con)

    for name in strategy_names:
        try:
            strategy_module = importlib.import_module(f"strategies.{name}.strategy")
            config_module = importlib.import_module(f"strategies.{name}.config")
        except ModuleNotFoundError as e:
            logger.error(f"skip strategy {name!r}: {e}")
            continue
        strategy_class = _discover_strategy_class(strategy_module)
        if strategy_class is None:
            logger.error(f"no BaseStrategy subclass in strategies/{name}/strategy.py")
            continue
        order_manager = OrderManager(
            client=client, logger=logger, md_logger=md,
            strategy_name=name, account_name=account_name,
        )
        strategy = strategy_class(
            client=client, order_manager=order_manager, logger=logger, config=config_module,
        )
        interval = getattr(config_module, "INTERVAL", "1m")
        timeframe = TimeFrame.Day if interval == "1d" else (
            TimeFrame.Hour if interval.endswith("h") else TimeFrame.Minute
        )
        try:
            bars = client.get_latest_bars(config_module.SYMBOLS, timeframe=timeframe)
            strategy.on_bar(bars)
        except Exception:
            logger.error(f"on_bar {name} failed:\n{traceback.format_exc()}")

    # Poll today's fills and update trade rows (mirror runner.py shutdown; pnl deferred to the
    # daily-pnl-aggregation Flight per SCHEMA-07 — pnl is nullable).
    try:
        today = dt.date.today()
        orders = client.trading.get_orders(GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=dt.datetime.combine(today, dt.time.min, tzinfo=dt.timezone.utc),
        ))
        for order in orders:
            if order.filled_at and order.filled_avg_price:
                md.update_fill(str(order.id), order.filled_at, float(order.filled_avg_price), None)
    except Exception as e:
        logger.error(f"fill polling failed: {e}")

    # Positions/portfolio are account-level at Alpaca but the schema attributes them per strategy.
    # Snapshot once per strategy in this account so each strategy_name carries its account state
    # (mirrors what N separate per-strategy runs would each record).
    try:
        positions = client.trading.get_all_positions()
        for name in strategy_names:
            md.snapshot_positions(positions, name, account_name)
    except Exception as e:
        logger.error(f"snapshot_positions failed: {e}")
    try:
        account = client.trading.get_account()
        for name in strategy_names:
            md.snapshot_portfolio(account, name, account_name)
    except Exception as e:
        logger.error(f"snapshot_portfolio failed: {e}")
