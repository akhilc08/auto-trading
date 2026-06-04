"""risk-monitor Flight unit tests on an in-memory DuckDB connection.

Mirrors tests/test_motherduck_logger.py: a fresh duckdb.connect() with the base trading tables
created via MotherDuckLogger(con=...), then risk_monitor.run(con).
"""
import datetime as dt
from zoneinfo import ZoneInfo

import duckdb

from core.motherduck_logger import MotherDuckLogger
from flights.risk import risk_monitor

_ET = ZoneInfo("America/New_York")


def _et_today():
    return dt.datetime.now(dt.timezone.utc).astimezone(_ET).date()


def _base_con():
    con = duckdb.connect()
    MotherDuckLogger(con=con)  # creates trading.main.{trades,positions,portfolio_snapshots,daily_pnl}
    return con


def _insert_position(con, account, strategy, symbol, qty, price, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.positions
            (snapshot_at, strategy_name, account_name, symbol, qty, avg_entry_price,
             current_price, unrealized_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        [snapshot_at, strategy, account, symbol, qty, price, price],
    )


def _insert_equity(con, account, strategy, equity, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.portfolio_snapshots
            (snapshot_at, strategy_name, account_name, equity, cash, buying_power)
        VALUES (?, ?, ?, ?, 0, 0)
        """,
        [snapshot_at, strategy, account, equity],
    )


def _insert_daily_pnl(con, account, strategy, date, realized, max_dd):
    con.execute(
        """
        INSERT INTO trading.main.daily_pnl
            (date, strategy_name, account_name, realized_pnl, trade_count, win_count,
             sharpe_7d, max_drawdown)
        VALUES (?, ?, ?, ?, 1, 1, NULL, ?)
        """,
        [date, strategy, account, realized, max_dd],
    )


def test_run_creates_risk_alerts_table():
    con = _base_con()
    risk_monitor.run(con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "risk_alerts" in {r[0] for r in tables}


def test_account_metrics_dedupe_per_strategy_duplication():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    # Same account positions snapshotted under TWO strategies (the _runner.py duplication).
    for strat in ("stat_arb", "stat_arb_v2"):
        _insert_position(con, "stat_arb", strat, "AAPL", 100, 200.0, t)  # $20k
        _insert_position(con, "stat_arb", strat, "MSFT", 50, 100.0, t)   # $5k
        _insert_equity(con, "stat_arb", strat, 50000.0, t)
    metrics = risk_monitor._account_metrics(con)
    assert "stat_arb" in metrics
    m = metrics["stat_arb"]
    assert abs(m["gross_ratio"] - 0.5) < 1e-6          # 25k / 50k (NOT doubled)
    assert abs(m["concentration"] - 0.4) < 1e-6        # 20k / 50k
    assert m["top_symbol"] == "AAPL"


def test_drawdown_metrics_latest_per_strategy():
    con = _base_con()
    _insert_daily_pnl(con, "stat_arb", "stat_arb", dt.date(2026, 6, 2), 100.0, 1000.0)
    _insert_daily_pnl(con, "stat_arb", "stat_arb", dt.date(2026, 6, 3), -50.0, 6000.0)  # latest
    dd = risk_monitor._drawdown_metrics(con)
    assert abs(dd[("stat_arb", "stat_arb")] - 6000.0) < 1e-6


def test_derive_alerts_severities():
    account_metrics = {
        "stat_arb": {"gross_ratio": 2.1, "concentration": 0.30, "top_symbol": "AAPL", "equity": 50000.0},
    }
    drawdown = {("stat_arb", "stat_arb"): 6000.0}  # 6000/50000 = 0.12 -> breach (>0.10)
    alerts = risk_monitor._derive_alerts(account_metrics, drawdown)
    by_type = {(a["account_name"], a["strategy_name"], a["alert_type"]): a for a in alerts}
    assert by_type[("stat_arb", "", "gross_exposure")]["severity"] == "breach"
    assert by_type[("stat_arb", "", "concentration")]["severity"] == "warn"
    assert by_type[("stat_arb", "stat_arb", "drawdown")]["severity"] == "breach"


def test_derive_alerts_below_warn_is_silent():
    account_metrics = {
        "stat_arb": {"gross_ratio": 1.0, "concentration": 0.10, "top_symbol": "AAPL", "equity": 50000.0},
    }
    drawdown = {("stat_arb", "stat_arb"): 1000.0}  # 0.02 -> below warn
    assert risk_monitor._derive_alerts(account_metrics, drawdown) == []


def test_run_writes_alerts_and_is_idempotent():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    for strat in ("stat_arb", "stat_arb_v2"):
        _insert_position(con, "stat_arb", strat, "AAPL", 100, 200.0, t)  # 20k
        _insert_position(con, "stat_arb", strat, "MSFT", 50, 100.0, t)   # 5k -> gross 25k
        _insert_equity(con, "stat_arb", strat, 10000.0, t)               # gross 2.5x -> breach
    risk_monitor.run(con)
    risk_monitor.run(con)  # second run must not duplicate
    rows = con.execute(
        "SELECT severity FROM trading.main.risk_alerts "
        "WHERE account_name='stat_arb' AND alert_type='gross_exposure'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "breach"


def test_run_clears_resolved_alerts():
    """A previously-written alert from an earlier run is removed when it no longer fires."""
    con = _base_con()
    risk_monitor.run(con)  # create the table (no data -> no alerts)
    today = _et_today()    # Flight stamps alert_date in ET
    stale = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    con.execute(
        risk_monitor._UPSERT_ALERT,
        [today, "stat_arb", "", "gross_exposure", "breach", 9.9, 2.0, "old", stale],
    )
    assert con.execute("SELECT count(*) FROM trading.main.risk_alerts").fetchone()[0] == 1
    risk_monitor.run(con)  # no breaching data this run -> stale alert must be cleared
    assert con.execute("SELECT count(*) FROM trading.main.risk_alerts").fetchone()[0] == 0


def test_closed_positions_excluded_from_gross():
    """A position absent from the latest snapshot batch (closed) must not count toward exposure."""
    con = _base_con()
    t0 = dt.datetime(2026, 6, 4, 14, 0, tzinfo=dt.timezone.utc)
    t1 = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)  # later batch
    _insert_position(con, "acct", "s1", "AAPL", 100, 200.0, t0)  # held at t0...
    _insert_position(con, "acct", "s1", "MSFT", 50, 100.0, t0)
    _insert_position(con, "acct", "s1", "MSFT", 50, 100.0, t1)   # ...AAPL closed; only MSFT at t1
    _insert_equity(con, "acct", "s1", 50000.0, t1)
    m = risk_monitor._account_metrics(con)["acct"]
    assert abs(m["gross_ratio"] - 0.1) < 1e-6   # 5k/50k (AAPL's 20k excluded)
    assert m["top_symbol"] == "MSFT"


def test_short_positions_count_toward_gross():
    """gross is sum of ABSOLUTE market values — shorts count (market-neutral books)."""
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    _insert_position(con, "acct", "s1", "AAPL", 100, 200.0, t)    # +20k long
    _insert_position(con, "acct", "s1", "TSLA", -100, 300.0, t)   # -30k short
    _insert_equity(con, "acct", "s1", 50000.0, t)
    m = risk_monitor._account_metrics(con)["acct"]
    assert abs(m["gross_ratio"] - 1.0) < 1e-6        # (20k + 30k)/50k, NOT net (-10k)
    assert m["top_symbol"] == "TSLA"                  # |30k| is largest
    assert abs(m["concentration"] - 0.6) < 1e-6       # 30k/50k


def test_multi_account_isolation():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    _insert_position(con, "A", "s", "AAPL", 100, 200.0, t)   # 20k
    _insert_equity(con, "A", "s", 100000.0, t)               # 0.2x
    _insert_position(con, "B", "s", "TSLA", 100, 300.0, t)   # 30k
    _insert_equity(con, "B", "s", 30000.0, t)                # 1.0x
    m = risk_monitor._account_metrics(con)
    assert abs(m["A"]["gross_ratio"] - 0.2) < 1e-6 and m["A"]["top_symbol"] == "AAPL"
    assert abs(m["B"]["gross_ratio"] - 1.0) < 1e-6 and m["B"]["top_symbol"] == "TSLA"


def test_severity_boundaries_inclusive():
    assert risk_monitor._severity(1.5, 1.5, 2.0) == "warn"      # exactly warn
    assert risk_monitor._severity(2.0, 1.5, 2.0) == "breach"    # exactly breach
    assert risk_monitor._severity(1.4999, 1.5, 2.0) is None     # just below warn
    assert risk_monitor._severity(0.05, 0.05, 0.10) == "warn"
    assert risk_monitor._severity(0.10, 0.05, 0.10) == "breach"


def test_drawdown_alert_for_flat_account():
    """An account with equity + a recorded drawdown but NO open positions must still alert."""
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    _insert_equity(con, "acct", "s1", 50000.0, t)                                  # flat: equity only
    _insert_daily_pnl(con, "acct", "s1", dt.date(2026, 6, 3), -100.0, 10000.0)     # 20% -> breach
    risk_monitor.run(con)
    rows = con.execute(
        "SELECT severity FROM trading.main.risk_alerts "
        "WHERE alert_type='drawdown' AND account_name='acct'"
    ).fetchall()
    assert len(rows) == 1 and rows[0][0] == "breach"


def test_equity_zero_produces_no_alerts():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    _insert_position(con, "acct", "s1", "AAPL", 100, 200.0, t)
    _insert_equity(con, "acct", "s1", 0.0, t)
    _insert_daily_pnl(con, "acct", "s1", dt.date(2026, 6, 3), -100.0, 10000.0)
    assert risk_monitor.run(con) == 0
    assert con.execute("SELECT count(*) FROM trading.main.risk_alerts").fetchone()[0] == 0
