"""Bundled MotherDuck write layer for execution Flights.

Re-implements the Phase 1 `core.motherduck_logger.MotherDuckLogger` write contracts so an
execution Flight is self-contained: idempotent `CREATE TABLE IF NOT EXISTS` DDL for the
SCHEMA-01/02/03 tables and the same write semantics (log_order ON CONFLICT DO NOTHING,
update_fill, snapshot_positions, snapshot_portfolio). Targets the SAME tables Phase 1 defines
(`trading.main.trades/positions/portfolio_snapshots`); it does not redefine them differently.

Takes a live `duckdb.connect("md:")` connection (the Flight owns the connection / token).
"""
import json
import warnings
from datetime import datetime, timezone


class FlightLogger:
    def __init__(self, con):
        self.con = con
        self._ensure_schema()

    def _ensure_schema(self):
        self.con.execute("CREATE DATABASE IF NOT EXISTS trading")
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
        # Per-strategy position state carried between one-shot Flight fires (JSON blob). Lets
        # stateful strategies (stat_arb, market_neutral) remember open positions / bars-held /
        # cooldown so they can manage exits and avoid re-stacking entries across runs.
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.strategy_state (
                strategy_name VARCHAR NOT NULL,
                account_name  VARCHAR NOT NULL,
                state_json    VARCHAR NOT NULL,
                updated_at    TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (strategy_name, account_name)
            )
        """)

    def log_order(self, order, strategy_name: str, account_name: str):
        if order is None:
            return
        # ON CONFLICT (order_id) DO NOTHING only — never an upsert that writes the conflict
        # column (DuckDB bug #16698 corrupts rows). Re-running the Flight does not duplicate.
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
        rows = self.con.execute(
            """
            UPDATE trading.main.trades
            SET filled_at = ?, filled_avg_price = ?, pnl = ?, status = 'filled'
            WHERE order_id = ?
            RETURNING order_id
            """,
            [filled_at, filled_avg_price, pnl, order_id],
        ).fetchall()
        if not rows:
            warnings.warn(
                f"update_fill: order_id={order_id!r} not found in trades table; fill record lost",
                RuntimeWarning,
                stacklevel=2,
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
                    float(position.current_price) if position.current_price is not None else None,
                    float(position.unrealized_pl) if position.unrealized_pl is not None else None,
                ],
            )

    def load_strategy_state(self, strategy_name: str, account_name: str) -> dict:
        rows = self.con.execute(
            "SELECT state_json FROM trading.main.strategy_state "
            "WHERE strategy_name = ? AND account_name = ?",
            [strategy_name, account_name],
        ).fetchall()
        if not rows or not rows[0][0]:
            return {}
        try:
            data = json.loads(rows[0][0])
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def save_strategy_state(self, strategy_name: str, account_name: str, state: dict):
        # ON CONFLICT updates the non-key columns only (never the PK) — DuckDB bug #16698.
        self.con.execute(
            """
            INSERT INTO trading.main.strategy_state (strategy_name, account_name, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (strategy_name, account_name) DO UPDATE SET
                state_json = EXCLUDED.state_json,
                updated_at = EXCLUDED.updated_at
            """,
            [strategy_name, account_name, json.dumps(state), datetime.now(timezone.utc)],
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
                float(account.equity) if account.equity is not None else None,
                float(account.cash) if account.cash is not None else None,
                float(account.buying_power) if account.buying_power is not None else None,
            ],
        )
