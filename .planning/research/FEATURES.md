# Feature Landscape: MotherDuck Dives and Flights for Trading Analytics

**Domain:** Cloud trading analytics — scheduled SQL aggregations and interactive dashboards on top of an Alpaca-based algo trading system
**Researched:** 2026-06-03 (rewritten via MotherDuck MCP tools — authoritative)
**Overall confidence:** HIGH

## MotherDuck Flights — Feature Details

Flights are Python programs on MotherDuck compute. For the aggregation pipeline:

**Flight: `daily-pnl-aggregation`**
- Runs post-market on a UTC cron (e.g. `"0 23 * * 1-5"` = 6 PM ET Mon–Fri)
- Connects to MotherDuck via `duckdb.connect("md:")` (token from `access_token_name`)
- Reads `trades` table, computes daily P&L, Sharpe, drawdown, win rate per strategy
- Writes results to `daily_pnl` table
- Must filter `WHERE status = 'filled'` to exclude pending orders
- Idempotent: use `INSERT OR REPLACE` / `ON CONFLICT ... DO UPDATE` so re-runs on same date don't duplicate

**Build pattern:**
```python
def main():
    con = duckdb.connect("md:")
    con.execute("""
        INSERT OR REPLACE INTO trading.main.daily_pnl
        SELECT
            CURRENT_DATE as date,
            strategy_name,
            account_name,
            SUM(pnl) as realized_pnl,
            COUNT(*) as trade_count,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_count
        FROM trading.main.trades
        WHERE status = 'filled'
          AND filled_at::DATE = CURRENT_DATE - INTERVAL 1 DAY
        GROUP BY strategy_name, account_name
    """)
```

## MotherDuck Dives — Feature Details

Dives are React components with live queries. Four target Dives:

### Dive 1: Trade Log (LOW complexity)
- Direct read from `trades` table
- Columns: symbol, side, qty, submitted_at, filled_avg_price, pnl, strategy_name
- Default filter: last 90 days
- Interactive filter by strategy (use `useDiveState` for URL-persistent selection)

### Dive 2: Live Positions (LOW complexity)
- Direct read from `positions` table, latest snapshot per strategy
- Columns: symbol, qty, avg_entry_price, current_price, unrealized_pnl
- Color-code unrealized_pnl: green (`#2d7a00`) if positive, red (`#bc1200`) if negative
- Use `N()` helper on all numeric values

### Dive 3: Equity Curve (LOW-MEDIUM complexity)
- Reads `daily_pnl`, computes cumulative SUM as running total
- LineChart with `type="linear"`, one line per strategy
- Time series gaps filled in SQL with `generate_series` LEFT JOIN
- Default 90-day window

### Dive 4: Strategy Comparison (MEDIUM-HIGH complexity)
- Reads `daily_pnl` for Sharpe, drawdown, win rate
- Reads `trades` for trade count
- Table display (not chart — <8 categories, table shows all metrics at once)
- Rows: strategies; columns: Sharpe 7d, max drawdown, win rate %, trade count, total P&L

## Schema Design

All tables need `strategy_name` and `account_name` from day one — cannot be added cleanly after data exists.

### `trades`
```sql
CREATE TABLE IF NOT EXISTS trading.main.trades (
    order_id        VARCHAR PRIMARY KEY,
    strategy_name   VARCHAR NOT NULL,
    account_name    VARCHAR NOT NULL,
    symbol          VARCHAR NOT NULL,
    side            VARCHAR NOT NULL,
    qty             DECIMAL(18,4) NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL,
    filled_at       TIMESTAMPTZ,
    filled_avg_price DECIMAL(18,4),
    pnl             DECIMAL(18,4),
    status          VARCHAR NOT NULL DEFAULT 'submitted'
)
```

### `positions`
```sql
CREATE TABLE IF NOT EXISTS trading.main.positions (
    snapshot_at      TIMESTAMPTZ NOT NULL,
    strategy_name    VARCHAR NOT NULL,
    account_name     VARCHAR NOT NULL,
    symbol           VARCHAR NOT NULL,
    qty              DECIMAL(18,4) NOT NULL,
    avg_entry_price  DECIMAL(18,4) NOT NULL,
    current_price    DECIMAL(18,4) NOT NULL,
    unrealized_pnl   DECIMAL(18,4) NOT NULL
)
```

### `portfolio_snapshots`
```sql
CREATE TABLE IF NOT EXISTS trading.main.portfolio_snapshots (
    snapshot_at   TIMESTAMPTZ NOT NULL,
    strategy_name VARCHAR NOT NULL,
    account_name  VARCHAR NOT NULL,
    equity        DECIMAL(18,4) NOT NULL,
    cash          DECIMAL(18,4) NOT NULL,
    buying_power  DECIMAL(18,4) NOT NULL
)
```

### `daily_pnl` (written by Flight)
```sql
CREATE TABLE IF NOT EXISTS trading.main.daily_pnl (
    date            DATE NOT NULL,
    strategy_name   VARCHAR NOT NULL,
    account_name    VARCHAR NOT NULL,
    realized_pnl    DECIMAL(18,4),
    trade_count     INTEGER,
    win_count       INTEGER,
    sharpe_7d       DECIMAL(8,4),
    max_drawdown    DECIMAL(8,4),
    PRIMARY KEY (date, strategy_name, account_name)
)
```

## Build Order

1. Schema DDL (all 4 tables) — blocks everything else
2. `MotherDuckLogger` in Python — blocks GitHub Actions and Flight
3. GitHub Actions strategy workflows — blocks real trade data
4. MotherDuck Flight (aggregation) — blocks equity curve and strategy comparison Dives
5. Dives — last, requires real data in tables

## Deferred to v1.1+

- Data freshness monitoring (60-day inactivity alert)
- Per-account equity curve filter (schema already supports it, just a Dive query change)
- Win rate by symbol breakdown
- Strategy correlation heatmap (high SQL complexity)
- Real-time streaming dashboards
