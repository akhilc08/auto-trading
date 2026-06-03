# Feature Landscape: MotherDuck Dives and Flights for Trading Analytics

**Domain:** Cloud trading analytics — scheduled SQL aggregations and interactive dashboards on top of an Alpaca-based algo trading system
**Researched:** 2026-06-02
**Overall confidence:** HIGH for Dives (well-documented), MEDIUM for "Flights" (term not in MotherDuck product — see clarification below)

---

## Critical Clarification: "Flights" Is Not a MotherDuck Product

"Flights" as a named MotherDuck feature does not exist. Extensive search through MotherDuck docs, release notes, blog, and product pages found no product called Flights. The term "Arrow Flight" appears in the DuckDB ecosystem (an Apache protocol for columnar data transfer), but that is unrelated.

**What "Flights" maps to in practice:** The PROJECT.md describes Flights as "scheduled SQL aggregation pipelines." In MotherDuck's actual product model, this is accomplished via:

1. **GitHub Actions with cron** — MotherDuck's own documentation explicitly recommends this pattern for scheduled SQL execution. The project already uses GitHub Actions for strategy execution, so the aggregation job is a natural addition to the same workflow.
2. **Scheduled queries (in-progress feature)** — MotherDuck has a feature request for native scheduled queries marked "in progress" as of February 2026. Not available yet.
3. **External orchestrators** — Airflow, Dagster, Prefect, Kestra are listed as official integrations, but add infrastructure the project explicitly avoids.

**Recommendation:** Implement "Flights" as a separate GitHub Actions job that runs a Python script executing DuckDB/MotherDuck SQL aggregation queries on a nightly cron. This costs nothing, requires no new infrastructure, and follows MotherDuck's documented pattern. The Python script connects via `duckdb.connect("md:?motherduck_token=...")` and runs the aggregation SQL.

---

## Table Stakes

Features users expect in a trading analytics layer. Missing = the system is not observable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `trades` table schema | Every downstream feature depends on it | Low | Must be written by `motherduck_logger.py` on every fill |
| `positions` table schema | Live positions Dive and P&L depend on it | Low | Snapshot on each strategy run |
| `portfolio_snapshots` table | Equity curve and drawdown require daily totals | Low | One row per account per day |
| Daily P&L aggregation SQL | Equity curve Dive reads from this | Low | Simple GROUP BY + SUM over trades |
| Max drawdown calculation | Industry-standard risk metric | Medium | Requires running max window function |
| Equity curve Dive | Most fundamental performance chart | Medium | Line chart, one series per strategy |
| Trade log Dive | Auditable record of every fill | Low | Sortable table, filterable by strategy/symbol |
| Strategy comparison Dive | Multi-strategy view of Sharpe, drawdown, win rate | High | Multiple derived metrics, multi-series chart |
| Live positions Dive | Current unrealized P&L per open position | Medium | Reads current Alpaca data or latest positions snapshot |

## Differentiators

Features that add meaningful analytical value beyond basic observability.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-account equity curve | 3 accounts (stat_arb, macro_vol, stock_alpha) need separate views | Low | Add `account` column to schema, filter in Dive |
| Win rate by symbol | Reveals which symbols are contributing alpha per strategy | Medium | Requires pairing entry/exit rows in trades table |
| Sharpe ratio SQL | Annualized risk-adjusted return without Python needed | Medium | `STDDEV` + `AVG` of daily returns × √252 |
| Strategy correlation heatmap | Shows if strategies are diversified or doubling up | High | Requires aligned daily returns per strategy |
| Drawdown recovery chart | Shows how long after a drawdown before new equity high | High | Multi-step window function calculation |

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time streaming Dives | Alpaca WebSocket data cannot flow through MotherDuck in real time; adds infra complexity | Refresh Dives on aggregation schedule (nightly or post-market) |
| Rewriting strategy logic as SQL | Alpaca order execution requires Python — SQL cannot call the brokerage API | Python executes trades and writes outcomes to MotherDuck; SQL only does analytics |
| Custom dashboard server (Grafana, Metabase, etc.) | Adds infra the project explicitly avoids; Dives are built-in | Use MotherDuck Dives exclusively |
| Bi-temporal tracking (as-of queries) | Adds schema complexity not needed at this stage | Simple insert timestamps are sufficient; rows are append-only |
| FX / multi-currency support | All Alpaca accounts operate in USD | Single-currency schema |

---

## Feature Dependencies

```
trades table (filled by motherduck_logger.py)
  └── trade log Dive (reads raw rows)
  └── daily P&L aggregation SQL (aggregates fills into daily_pnl table)
        └── equity curve Dive (reads daily_pnl)
        └── drawdown calc SQL (window function on daily_pnl)
              └── strategy comparison Dive (reads drawdown + Sharpe)

positions table (filled by motherduck_logger.py)
  └── live positions Dive (reads latest snapshot per symbol)

portfolio_snapshots table (filled by aggregation job)
  └── equity curve Dive (alternative: read from snapshots instead of daily_pnl)
  └── drawdown calc SQL
```

The aggregation job ("Flights") is the only dependency between Python writes and the analytics Dives. If the aggregation job has not run, the equity curve and comparison Dives show stale or empty data. The trade log and live positions Dives can read directly from the source tables with no dependency on the aggregation job.

---

## Dives: Technical Specification

**What Dives are:** React components that live inside MotherDuck and query live MotherDuck data on every load. They are not static exports — they re-execute SQL on render.

**How they are created:**
- Via AI agent: describe what you want and Claude (connected via MotherDuck MCP) generates the React + SQL and calls `MD_CREATE_DIVE`.
- Via SQL directly: `SELECT * FROM MD_CREATE_DIVE(title='...', content='<JSX>')`.
- Via version-controlled `.tsx` files in a repo with CI/CD pushing updates via `MD_UPDATE_DIVE_CONTENT`.

**Core React API (confirmed via official docs and Context7):**

```tsx
import { useSQLQuery } from "@motherduck/react-sql-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function Dive() {
  const { data, isLoading, isError } = useSQLQuery(`
    SELECT date, strategy, cumulative_pnl
    FROM daily_pnl
    ORDER BY date
  `);
  // render with recharts
}
```

- `useSQLQuery(sql, options?)` — executes SQL and returns `{ data, isLoading, isError, error }`. The `select` option transforms rows before return.
- `useDiveState(key, defaultValue)` — shareable URL-encoded state for filters, selected tabs, date ranges. Allows sharing a Dive URL with state intact.
- `exportAs` / `useExport` hooks — from `@motherduck/react-sql-query`, enables CSV/Parquet/JSON export buttons in the Dive.

**Available chart libraries (confirmed):**
- `recharts` — primary charting library. `LineChart`, `BarChart`, `ScatterChart`, `AreaChart`, `ComposedChart`, `ResponsiveContainer`, `Tooltip`, `Legend`, `XAxis`, `YAxis`, `CartesianGrid`, `ReferenceLine`.
- `D3` — available for custom visualizations.
- Full React ecosystem — any logic expressible in React is valid.

**Rendering environment:** Same React components as the MotherDuck UI. Runs inside the MotherDuck workspace alongside SQL notebooks. Sharing is via URL. Cannot be iframed into external sites due to header/permission constraints (confirmed as of current docs).

**CRUD SQL functions:**
- `MD_CREATE_DIVE(title, content, description?)` — creates new Dive, returns `id`, `title`, `current_version`
- `MD_UPDATE_DIVE_CONTENT(id, content, description?)` — updates React code, creates new version
- `MD_UPDATE_DIVE_METADATA(id, title?, description?)` — updates title/description without versioning
- `MD_GET_DIVE(id)` — retrieves Dive by ID
- `MD_LIST_DIVES()` — lists all Dives with pagination
- `MD_DELETE_DIVE(id)` — permanently removes

---

## Schema Design

The schema must support: multi-strategy queries, per-account filtering, trade-level P&L, and equity curve aggregation. All three accounts (`stat_arb`, `macro_vol`, `stock_alpha`) must be distinguishable.

### `trades` table

```sql
CREATE TABLE IF NOT EXISTS trades (
    id           VARCHAR PRIMARY KEY,        -- Alpaca order ID (UUID)
    strategy     VARCHAR NOT NULL,           -- e.g. 'trend_following', 'stat_arb'
    account      VARCHAR NOT NULL,           -- e.g. 'macro_vol', 'stat_arb', 'stock_alpha'
    symbol       VARCHAR NOT NULL,           -- e.g. 'AAPL'
    side         VARCHAR NOT NULL,           -- 'buy' | 'sell'
    qty          DOUBLE NOT NULL,
    filled_qty   DOUBLE,
    filled_price DOUBLE,                     -- filled_avg_price from Alpaca Order model
    notional     DOUBLE,                     -- filled_qty * filled_price
    status       VARCHAR,                    -- 'filled' | 'canceled' | 'partial'
    submitted_at TIMESTAMPTZ,
    filled_at    TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

Source fields map directly from the Alpaca `Order` model: `id`, `symbol`, `side`, `qty`, `filled_qty`, `filled_avg_price`, `status`, `submitted_at`, `filled_at`.

### `positions` table

```sql
CREATE TABLE IF NOT EXISTS positions (
    snapshot_at     TIMESTAMPTZ NOT NULL,    -- when this snapshot was taken
    strategy        VARCHAR NOT NULL,
    account         VARCHAR NOT NULL,
    symbol          VARCHAR NOT NULL,
    qty             DOUBLE NOT NULL,         -- signed: negative = short
    avg_entry_price DOUBLE,
    current_price   DOUBLE,
    market_value    DOUBLE,
    cost_basis      DOUBLE,
    unrealized_pl   DOUBLE,
    unrealized_plpc DOUBLE,                  -- percentage
    PRIMARY KEY (snapshot_at, strategy, symbol)
);
```

Source fields map from the Alpaca `Position` model: `qty`, `avg_entry_price`, `current_price`, `market_value`, `cost_basis`, `unrealized_pl`, `unrealized_plpc`.

### `portfolio_snapshots` table

Written by the nightly aggregation job. One row per account per day.

```sql
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_date DATE NOT NULL,
    account       VARCHAR NOT NULL,
    strategy      VARCHAR,                   -- NULL means account-level rollup
    total_pnl     DOUBLE,                    -- realized P&L for the day
    cumulative_pnl DOUBLE,                   -- running total
    open_positions INTEGER,
    PRIMARY KEY (snapshot_date, account, strategy)
);
```

### `daily_pnl` table (aggregation output)

Written by the nightly job. This is what Dives query.

```sql
CREATE TABLE IF NOT EXISTS daily_pnl (
    date           DATE NOT NULL,
    strategy       VARCHAR NOT NULL,
    account        VARCHAR NOT NULL,
    daily_return   DOUBLE,                   -- sum of notional for the day
    cumulative_pnl DOUBLE,                   -- running cumulative
    trade_count    INTEGER,
    PRIMARY KEY (date, strategy)
);
```

---

## Analytics SQL Patterns (DuckDB)

All patterns verified against DuckDB official docs and MotherDuck Context7 corpus.

### Equity Curve (cumulative P&L over time)

```sql
SELECT
    date,
    strategy,
    SUM(daily_return) OVER (
        PARTITION BY strategy
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_pnl
FROM daily_pnl
ORDER BY strategy, date;
```

### Max Drawdown (per strategy)

```sql
WITH running AS (
    SELECT
        date,
        strategy,
        cumulative_pnl,
        MAX(cumulative_pnl) OVER (
            PARTITION BY strategy
            ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak
    FROM daily_pnl
),
drawdowns AS (
    SELECT
        strategy,
        MIN(cumulative_pnl - running_peak) AS max_drawdown
    FROM running
    GROUP BY strategy
)
SELECT * FROM drawdowns;
```

### Sharpe Ratio (annualized)

```sql
SELECT
    strategy,
    AVG(daily_return) / NULLIF(STDDEV(daily_return), 0) * SQRT(252) AS sharpe_ratio
FROM daily_pnl
GROUP BY strategy;
```

### Win Rate (requires trade-level pairing — moderate complexity)

Win rate requires pairing each sell with its corresponding buy. The simplest approach is to compute it at logging time in Python (compare fill price to entry price and write a `pnl` column to `trades`). If `trades` includes a `pnl` column:

```sql
SELECT
    strategy,
    COUNT(*) FILTER (WHERE side = 'sell' AND pnl > 0) * 1.0 /
    NULLIF(COUNT(*) FILTER (WHERE side = 'sell'), 0) AS win_rate
FROM trades
GROUP BY strategy;
```

If `pnl` is not pre-computed, pairing buys and sells in SQL requires a self-join or LAG-based approach and becomes HIGH complexity. Pre-computing `pnl` in Python at fill time is the correct decision.

### Daily P&L Aggregation (the "Flights" job SQL)

```sql
INSERT OR REPLACE INTO daily_pnl
SELECT
    CAST(filled_at AS DATE) AS date,
    strategy,
    account,
    SUM(CASE WHEN side = 'sell' THEN notional ELSE -notional END) AS daily_return,
    0 AS cumulative_pnl,    -- recomputed below
    COUNT(*) AS trade_count
FROM trades
WHERE filled_at IS NOT NULL
GROUP BY 1, 2, 3;

-- Recompute cumulative (DuckDB does not support window UPDATE, so do as a replace)
INSERT OR REPLACE INTO daily_pnl
SELECT
    date, strategy, account, daily_return, trade_count,
    SUM(daily_return) OVER (
        PARTITION BY strategy
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_pnl
FROM daily_pnl
ORDER BY strategy, date;
```

---

## Four Dives: Complexity and Scope

### 1. Equity Curve Dive
**Reads from:** `daily_pnl`
**Chart type:** `AreaChart` or `LineChart` from recharts, one series per strategy
**Interactivity:** `useDiveState` for date range picker, strategy filter
**Complexity:** LOW — single SQL query, standard recharts pattern
**Dependency:** Aggregation job must have run at least once

### 2. Trade Log Dive
**Reads from:** `trades`
**Chart type:** Sortable, filterable table
**Interactivity:** Filter by strategy, account, symbol, date range; sort by filled_at or pnl
**Complexity:** LOW — no aggregation, direct table read with `useDiveState` filters
**Dependency:** None beyond trades table having rows

### 3. Strategy Comparison Dive
**Reads from:** `daily_pnl` (for Sharpe and equity), `trades` (for win rate if pnl column present)
**Chart type:** Bar chart for Sharpe/drawdown, summary stat cards for win rate and trade count
**Interactivity:** Toggle metric, select date range
**Complexity:** MEDIUM — multiple SQL queries via multiple `useSQLQuery` calls, layout complexity
**Dependency:** Aggregation job must have run; `trades.pnl` column required for win rate

### 4. Live Positions Dive
**Reads from:** `positions` (latest snapshot per symbol)
**Chart type:** Table showing open positions with unrealized P&L color-coded (green/red)
**Interactivity:** Filter by account/strategy
**Complexity:** LOW-MEDIUM — needs a `WHERE snapshot_at = MAX(snapshot_at)` subquery or a view
**Dependency:** None beyond positions table; most recent snapshot sufficient

---

## "Flights" Implementation Pattern

Since MotherDuck native scheduled queries are not yet released, implement as a GitHub Actions workflow job:

```yaml
# .github/workflows/aggregate.yml
on:
  schedule:
    - cron: '0 22 * * 1-5'   # 10pm UTC = 6pm ET, after market close
jobs:
  aggregate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install duckdb
      - run: python core/aggregate.py
        env:
          MOTHERDUCK_TOKEN: ${{ secrets.MOTHERDUCK_TOKEN }}
```

`core/aggregate.py` connects to MotherDuck and runs the daily P&L aggregation SQL. This is the only new Python file needed for the "Flights" functionality.

---

## MVP Recommendation

Build in this order — each step unblocks the next:

1. **Schema + logger** — `trades`, `positions` tables; `motherduck_logger.py` writes fills. Unblocks all Dives.
2. **Trade log Dive** — reads directly from `trades`, no aggregation needed. Fastest to ship, validates schema.
3. **Live positions Dive** — reads from `positions`, no aggregation needed.
4. **Aggregation job ("Flights")** — GitHub Actions cron job writing `daily_pnl`. Unblocks equity curve and comparison Dives.
5. **Equity curve Dive** — reads from `daily_pnl`, straightforward line chart.
6. **Strategy comparison Dive** — most complex; requires all prior pieces.

Defer: strategy correlation heatmap, drawdown recovery chart — these are differentiators with high complexity and no dependency from other features.

---

## Sources

- MotherDuck Dives documentation: https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/
- MD_CREATE_DIVE SQL function: https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/
- save_dive MCP tool (recharts confirmed): https://motherduck.com/docs/sql-reference/mcp/save-dive
- MotherDuck GitHub Actions cron pattern: https://motherduck.com/docs/key-tasks/data-warehousing/orchestration/github-action-cron
- Scheduled queries feature request (in-progress, not released): https://motherduck.canny.io/feature-requests/p/scheduled-queries-notebooks
- DuckDB window functions: https://duckdb.org/docs/current/sql/functions/window_functions
- Alpaca Order model fields: https://alpaca.markets/sdks/python/api_reference/trading/models.html
- MotherDuck orchestration docs: https://motherduck.com/docs/key-tasks/data-warehousing/
- Confidence levels: Dives API HIGH (Context7 + official docs); "Flights" clarification HIGH (absence confirmed across all official sources); DuckDB SQL patterns HIGH (official docs); schema design MEDIUM (derived from Alpaca SDK fields + trading system conventions)
