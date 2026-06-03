"""MotherDuck write layer for trade/position/portfolio data.

Connects to MotherDuck (or accepts an injected connection for tests) and runs
idempotent CREATE TABLE IF NOT EXISTS DDL for all 4 tables on construction.

No import-time side effects: importing this module does NOT open any connection
(SCHEMA-10 — graceful degradation when MOTHERDUCK_TOKEN is absent).
"""
import os
from datetime import datetime, timezone

import duckdb


class MotherDuckLogger:
    def __init__(self, token: str = None, con=None):
        if con is not None:
            self.con = con
        else:
            self.con = duckdb.connect("md:", config={"motherduck_token": token})
        self._ensure_schema()

    def _ensure_schema(self):
        # CREATE DATABASE is MotherDuck DDL; fall back to ATTACH for in-memory tests.
        try:
            self.con.execute("CREATE DATABASE IF NOT EXISTS trading")
        except Exception:
            self.con.execute("ATTACH IF NOT EXISTS ':memory:' AS trading")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.trades (
                order_id         VARCHAR PRIMARY KEY,
                strategy_name    VARCHAR NOT NULL,
                account_name     VARCHAR NOT NULL,
                symbol           VARCHAR NOT NULL,
                side             VARCHAR NOT NULL,
                qty              DECIMAL(18,4) NOT NULL,
                submitted_at     TIMESTAMPTZ NOT NULL,
                filled_at        TIMESTAMPTZ,
                filled_avg_price DECIMAL(18,4),
                pnl              DECIMAL(18,4),
                status           VARCHAR NOT NULL DEFAULT 'submitted'
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.positions (
                snapshot_at      TIMESTAMPTZ NOT NULL,
                strategy_name    VARCHAR NOT NULL,
                account_name     VARCHAR NOT NULL,
                symbol           VARCHAR NOT NULL,
                qty              DECIMAL(18,4) NOT NULL,
                avg_entry_price  DECIMAL(18,4) NOT NULL,
                current_price    DECIMAL(18,4),
                unrealized_pnl   DECIMAL(18,4)
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.portfolio_snapshots (
                snapshot_at   TIMESTAMPTZ NOT NULL,
                strategy_name VARCHAR NOT NULL,
                account_name  VARCHAR NOT NULL,
                equity        DECIMAL(18,4),
                cash          DECIMAL(18,4),
                buying_power  DECIMAL(18,4)
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.daily_pnl (
                date           DATE NOT NULL,
                strategy_name  VARCHAR NOT NULL,
                account_name   VARCHAR NOT NULL,
                realized_pnl   DECIMAL(18,4),
                trade_count    INTEGER,
                win_count      INTEGER,
                sharpe_7d      DECIMAL(18,6),
                max_drawdown   DECIMAL(18,6),
                PRIMARY KEY (date, strategy_name, account_name)
            )
        """)

    def log_order(self, order, strategy_name: str, account_name: str):
        if order is None:
            return
        self.con.execute(
            """
            INSERT INTO trading.main.trades
                (order_id, strategy_name, account_name, symbol, side, qty, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted')
            ON CONFLICT (order_id) DO NOTHING
            """,
            [
                str(order.id),
                strategy_name,
                account_name,
                order.symbol,
                str(order.side.value),
                float(order.qty),
                order.submitted_at,
            ],
        )

    def update_fill(self, order_id: str, filled_at, filled_avg_price, pnl):
        self.con.execute(
            """
            UPDATE trading.main.trades
            SET filled_at = ?, filled_avg_price = ?, pnl = ?, status = 'filled'
            WHERE order_id = ?
            """,
            [filled_at, filled_avg_price, pnl, order_id],
        )

    def snapshot_positions(self, positions, strategy_name: str, account_name: str):
        now = datetime.now(timezone.utc)
        for position in positions:
            self.con.execute(
                """
                INSERT INTO trading.main.positions
                    (snapshot_at, strategy_name, account_name, symbol,
                     qty, avg_entry_price, current_price, unrealized_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    now,
                    strategy_name,
                    account_name,
                    position.symbol,
                    float(position.qty),
                    float(position.avg_entry_price),
                    float(position.current_price) if position.current_price else None,
                    float(position.unrealized_pl) if position.unrealized_pl else None,
                ],
            )

    def snapshot_portfolio(self, account, strategy_name: str, account_name: str):
        self.con.execute(
            """
            INSERT INTO trading.main.portfolio_snapshots
                (snapshot_at, strategy_name, account_name, equity, cash, buying_power)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                datetime.now(timezone.utc),
                strategy_name,
                account_name,
                float(account.equity) if account.equity else None,
                float(account.cash) if account.cash else None,
                float(account.buying_power) if account.buying_power else None,
            ],
        )
