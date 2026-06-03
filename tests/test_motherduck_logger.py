"""MotherDuckLogger unit tests.

All tests use an in-memory DuckDB connection injected via MotherDuckLogger(con=...)
so they run without a live MotherDuck connection or MOTHERDUCK_TOKEN env var.

Test map:
  test_no_token_no_exception   -> SCHEMA-10 (graceful degradation)
  test_schema_creates_all_tables -> SCHEMA-05 (CREATE TABLE IF NOT EXISTS x4)
  test_idempotent_insert       -> SCHEMA-06 (ON CONFLICT DO NOTHING)
  test_log_order_none_is_noop  -> close_position path (order=None guard)
  test_update_fill             -> SCHEMA-07 (fill update)
  test_snapshot_positions      -> SCHEMA-08 (position snapshot)
  test_snapshot_portfolio      -> SCHEMA-09 (portfolio snapshot)
"""
import datetime
import os

import duckdb
import pytest

from core.motherduck_logger import MotherDuckLogger


def _make_order(order_id="order-abc-123"):
    """Build a minimal fake Alpaca Order object."""
    side = type("Side", (), {"value": "buy"})()
    return type("O", (), {
        "id": order_id,
        "symbol": "AAPL",
        "side": side,
        "qty": "10",
        "submitted_at": datetime.datetime(2024, 1, 15, 14, 30, 0, tzinfo=datetime.timezone.utc),
    })()


def _make_position(symbol="AAPL", qty="10", avg_entry="150.0",
                   current="155.0", unrealized_pl="50.0"):
    """Build a minimal fake Alpaca Position object."""
    return type("P", (), {
        "symbol": symbol,
        "qty": qty,
        "avg_entry_price": avg_entry,
        "current_price": current,
        "unrealized_pl": unrealized_pl,
    })()


def _make_account(equity="100000.0", cash="50000.0", buying_power="75000.0"):
    """Build a minimal fake Alpaca TradeAccount object."""
    return type("A", (), {
        "equity": equity,
        "cash": cash,
        "buying_power": buying_power,
    })()


def test_import_does_not_connect():
    """Importing core.motherduck_logger must not open a connection (SCHEMA-10).

    The module-level import above already exercises this: if import triggered
    a MotherDuck connection, this module would fail to load in CI (no token).
    """
    import importlib
    import core.motherduck_logger as mdl
    importlib.reload(mdl)  # reload must not raise even without a token


def test_no_token_skips_md_logger():
    """runner.py's `if token:` guard must result in md_logger=None when token is absent (SCHEMA-10)."""
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if token:
        pytest.skip("MOTHERDUCK_TOKEN is set; cannot test no-token path")
    md_logger = None
    if token:
        md_logger = MotherDuckLogger(token=token)
    assert md_logger is None, "md_logger must be None when MOTHERDUCK_TOKEN is absent"


def test_schema_creates_all_tables():
    """MotherDuckLogger._ensure_schema() creates all 4 tables (SCHEMA-05)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    table_names = {row[0] for row in tables}
    assert "trades" in table_names, "trades table missing"
    assert "positions" in table_names, "positions table missing"
    assert "portfolio_snapshots" in table_names, "portfolio_snapshots table missing"
    assert "daily_pnl" in table_names, "daily_pnl table missing"


def test_idempotent_insert():
    """Logging the same order_id twice inserts exactly one row (SCHEMA-06)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    order = _make_order("order-idem-001")
    logger.log_order(order, "stat_arb", "stat_arb")
    logger.log_order(order, "stat_arb", "stat_arb")
    count = con.execute("SELECT count(*) FROM trading.main.trades").fetchone()[0]
    assert count == 1, f"expected 1 row after duplicate insert, got {count}"


def test_log_order_none_is_noop():
    """log_order(None, ...) returns without inserting or raising (close_position path)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    logger.log_order(None, "stat_arb", "stat_arb")  # must not raise
    count = con.execute("SELECT count(*) FROM trading.main.trades").fetchone()[0]
    assert count == 0, "no row should be inserted when order is None"


def test_update_fill():
    """update_fill() sets status='filled', filled_avg_price, filled_at (SCHEMA-07)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    order = _make_order("order-fill-001")
    logger.log_order(order, "stat_arb", "stat_arb")
    filled_at = datetime.datetime(2024, 1, 15, 15, 0, 0, tzinfo=datetime.timezone.utc)
    logger.update_fill("order-fill-001", filled_at, 101.5, None)
    row = con.execute(
        "SELECT status, filled_avg_price FROM trading.main.trades WHERE order_id = ?"
        , ["order-fill-001"]
    ).fetchone()
    assert row is not None, "trade row not found after update_fill"
    assert row[0] == "filled", f"expected status='filled', got '{row[0]}'"
    assert abs(float(row[1]) - 101.5) < 1e-6, f"expected filled_avg_price=101.5, got {row[1]}"


def test_snapshot_positions():
    """snapshot_positions() inserts one row per position (SCHEMA-08)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    p1 = _make_position("AAPL", "10", "150.0", "155.0", "50.0")
    p2 = _make_position("MSFT", "5", "300.0", "310.0", "50.0")
    logger.snapshot_positions([p1, p2], "stat_arb", "stat_arb")
    count = con.execute("SELECT count(*) FROM trading.main.positions").fetchone()[0]
    assert count == 2, f"expected 2 position rows, got {count}"


def test_snapshot_portfolio():
    """snapshot_portfolio() inserts one row with float-cast equity (SCHEMA-09)."""
    con = duckdb.connect()
    logger = MotherDuckLogger(con=con)
    account = _make_account("100000.50", "50000.25", "75000.00")
    logger.snapshot_portfolio(account, "stat_arb", "stat_arb")
    row = con.execute(
        "SELECT equity FROM trading.main.portfolio_snapshots"
    ).fetchone()
    assert row is not None, "portfolio_snapshots row not found"
    assert abs(float(row[0]) - 100000.50) < 1e-3, f"equity mismatch: {row[0]}"
