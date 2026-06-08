"""benchmark-load Flight unit tests on an in-memory DuckDB connection."""
import datetime as dt

import duckdb
import pytest

from core.motherduck_logger import MotherDuckLogger
from flights.benchmark import load_benchmark


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSecretCon:
    """Minimal con stub returning one duckdb_secrets() row (or none)."""
    def __init__(self, secret_string):
        self._secret_string = secret_string

    def execute(self, sql, params=None):
        rows = [(self._secret_string,)] if self._secret_string is not None else []
        return _FakeResult(rows)


def _base_con():
    con = duckdb.connect()
    MotherDuckLogger(con=con)  # creates the trading database + base tables
    return con


def _fake_bar(ts, close):
    return type("Bar", (), {"timestamp": ts, "close": close})()


class _FakeClient:
    """Stand-in for AlpacaClient.get_historical_bars returning {symbol: [Bar,...]}."""
    def get_historical_bars(self, symbols, n_days, timeframe=None):
        return {
            s: [
                _fake_bar(dt.datetime(2026, 6, 1, 4, 0, tzinfo=dt.timezone.utc), 500.0),
                _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 505.0),
            ]
            for s in symbols
        }


def test_run_creates_benchmark_prices_table():
    con = _base_con()
    load_benchmark.ensure_schema(con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "benchmark_prices" in {r[0] for r in tables}


def test_upsert_bars_inserts_and_dedupes():
    con = _base_con()
    load_benchmark.ensure_schema(con)
    bars = [
        _fake_bar(dt.datetime(2026, 6, 1, 4, 0, tzinfo=dt.timezone.utc), 500.0),
        _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 505.0),
    ]
    load_benchmark._upsert_bars(con, "SPY", bars)
    # re-run with a corrected close for 2026-06-02 -> updates, not duplicates
    load_benchmark._upsert_bars(con, "SPY", [
        _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 506.0),
    ])
    rows = con.execute(
        "SELECT date, close FROM trading.main.benchmark_prices WHERE symbol='SPY' ORDER BY date"
    ).fetchall()
    assert len(rows) == 2
    assert str(rows[0][0]) == "2026-06-01"
    assert abs(float(rows[1][1]) - 506.0) < 1e-6   # updated close


def test_run_loads_symbols_from_client():
    con = _base_con()
    written = load_benchmark.run(con, _FakeClient(), symbols=["SPY"], n_days=10)
    assert written == 2
    n = con.execute(
        "SELECT count(*) FROM trading.main.benchmark_prices WHERE symbol='SPY'"
    ).fetchone()[0]
    assert n == 2


def test_read_alpaca_secret_parses_headers_with_equals():
    # secret value containing '=' must survive (split on first '=' only)
    s = ("name=alpaca_stat_arb;type=http;provider=config;"
         "extra_http_headers={api_key=AKID123, secret_key=SEC=ret=eq}")
    api_key, secret_key = load_benchmark._read_alpaca_secret(_FakeSecretCon(s), "alpaca_stat_arb")
    assert api_key == "AKID123"
    assert secret_key == "SEC=ret=eq"


def test_read_alpaca_secret_missing_raises():
    with pytest.raises(RuntimeError):
        load_benchmark._read_alpaca_secret(_FakeSecretCon(None), "nope")


def test_read_alpaca_secret_no_headers_raises():
    s = "name=alpaca_stat_arb;type=http;provider=config"  # secret exists but no headers block
    with pytest.raises(RuntimeError, match="no extra_http_headers"):
        load_benchmark._read_alpaca_secret(_FakeSecretCon(s), "alpaca_stat_arb")


def test_read_alpaca_secret_partial_credentials_raises():
    s = "name=alpaca_stat_arb;type=http;extra_http_headers={api_key=AK}"  # secret_key absent
    with pytest.raises(RuntimeError, match="missing api_key/secret_key"):
        load_benchmark._read_alpaca_secret(_FakeSecretCon(s), "alpaca_stat_arb")
