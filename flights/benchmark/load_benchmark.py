"""benchmark-load Flight.

Fetches SPY (and any configured) daily bars from Alpaca and upserts them into
trading.main.benchmark_prices for alpha/beta analysis. Reads market data via the existing
alpaca_stat_arb MotherDuck secret.

SELF-CONTAINED: MotherDuck Flights run a single source file (MD_CREATE_FLIGHT stores one
`source_code` string), so this module must not import other repo modules. The secret-read and
IEX data client are inlined here (mirroring flights/exec/_runner.py) so the file deploys as-is
via `motherduck flight publish`. Only third-party deps are duckdb + alpaca-py.
"""
import datetime
import re

import duckdb
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

BENCHMARK_SYMBOLS = ["SPY"]
LOOKBACK_TRADING_DAYS = 400
SECRET_NAME = "alpaca_stat_arb"

DDL = """
CREATE TABLE IF NOT EXISTS trading.main.benchmark_prices (
    date   DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    close  DECIMAL(18,4) NOT NULL,
    PRIMARY KEY (date, symbol)
)
"""

_UPSERT = """
INSERT INTO trading.main.benchmark_prices (date, symbol, close)
VALUES (?, ?, ?)
ON CONFLICT (date, symbol) DO UPDATE SET close = EXCLUDED.close
"""


def _read_alpaca_secret(con, secret_name: str):
    """Read api_key/secret_key from the named MotherDuck secret (same mechanism as the exec Flights).

    Credentials are stored as EXTRA_HTTP_HEADERS entries on a TYPE http secret; they read back in
    plaintext via duckdb_secrets().secret_string. Values are split on the first '=' so credential
    values containing '=' survive.
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


class _BenchmarkDataClient:
    """Minimal Alpaca daily-bar reader on the free IEX feed (mirrors core.AlpacaClient's wide
    lookback). Only the historical-bars path is needed for benchmark loading."""

    def __init__(self, api_key: str, secret_key: str):
        self.data = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

    def get_historical_bars(self, symbols, n_days, timeframe=TimeFrame.Day):
        # 1.5x converts trading days to calendar days (weekends/holidays); +14 day cushion.
        calendar_days = int(n_days * 1.5) + 14
        start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=calendar_days)
        # Adjustment.ALL = split + dividend adjusted (total-return) closes, so SPY ex-dividend /
        # split dates don't inject spurious one-day returns into the alpha/beta return regression.
        req = StockBarsRequest(
            symbol_or_symbols=symbols, timeframe=timeframe, start=start,
            feed=DataFeed.IEX, adjustment=Adjustment.ALL,
        )
        return self.data.get_stock_bars(req).data


def ensure_schema(con):
    con.execute(DDL)


def _upsert_bars(con, symbol, bars):
    """Upsert Alpaca bars (objects with .timestamp datetime and .close) for one symbol.
    Returns the number of bars written."""
    n = 0
    for bar in bars:
        con.execute(_UPSERT, [bar.timestamp.date(), symbol, float(bar.close)])
        n += 1
    return n


def run(con, client, symbols=BENCHMARK_SYMBOLS, n_days=LOOKBACK_TRADING_DAYS):
    ensure_schema(con)
    data = client.get_historical_bars(symbols, n_days, timeframe=TimeFrame.Day)
    written = 0
    for symbol in symbols:
        written += _upsert_bars(con, symbol, data.get(symbol, []))
    return written


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    api_key, secret_key = _read_alpaca_secret(con, SECRET_NAME)
    client = _BenchmarkDataClient(api_key, secret_key)
    written = run(con, client)
    print(f"benchmark_prices rows written: {written}")


if __name__ == "__main__":
    main()
