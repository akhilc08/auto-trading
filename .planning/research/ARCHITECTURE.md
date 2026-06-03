# Architecture Patterns

**Project:** auto-trading MotherDuck cloud layer
**Researched:** 2026-06-02
**Confidence:** HIGH (core integration points from direct code inspection; MotherDuck Python API confirmed via official docs)

---

## Critical Finding: "Flights" Does Not Exist as a MotherDuck Feature

Research across MotherDuck's product pages, ecosystem page, SQL reference, and release notes found **no product feature called "Flights."** The term appears only as a sample dataset name in DuckDB/MotherDuck tutorials. MotherDuck's actual products are: cloud DuckDB execution (Ducklings), Shares (zero-copy read-only clones), Dives (AI-powered interactive visualizations), and an MCP Server. There is no native scheduled query runner product.

**Implication:** The "Flights: scheduled SQL aggregation pipeline" capability referenced in PROJECT.md does not exist as a MotherDuck product. This scope item needs to be replaced with the correct approach: run aggregation SQL from GitHub Actions as a post-execution step (Python calls `con.sql(...)` to aggregate after each strategy run), or schedule a dedicated aggregation workflow in GitHub Actions. SQL for analytics stays in Python-called DuckDB; MotherDuck is the storage layer, not the orchestration layer.

---

## Recommended Architecture

```
runner.py
  ├── get_logger(strategy)          # file logger unchanged
  ├── MotherDuckLogger(strategy)    # NEW: injected at construction
  └── strategy_class(
        client,
        order_manager,             # receives md_logger via order_manager or direct
        logger,
        config
      )

OrderManager
  └── buy/sell/short_sell/buy_to_cover/close_position
        └── on return: order_manager calls self.md_logger.log_order(order)  # NEW

MotherDuckLogger
  ├── log_order(order, symbol, side, qty, strategy)    # writes trades table
  ├── snapshot_positions(strategy)                      # writes positions table
  └── snapshot_portfolio(strategy)                      # writes portfolio_snapshots table

GitHub Actions (.github/workflows/)
  ├── run_strategy.yml              # reusable workflow (workflow_call)
  └── per-account workflows:
        ├── stat_arb.yml            # cron: stat_arb, stat_arb_v2, stat_arb_v3, market_neutral, market_neutral_v2
        ├── macro_vol.yml           # cron: trend_following, trend_following_v2, regime_switching, vol_risk_premium
        └── stock_alpha.yml         # cron: multi_factor_equity, multi_factor_equity_v2, post_earnings_drift

MotherDuck Schema (trading database)
  ├── trades              (order fills)
  ├── positions           (open positions snapshots)
  └── portfolio_snapshots (account-level equity snapshots)
```

---

## Integration Points in Existing Code

### Where to Hook: OrderManager, not BaseStrategy

The correct injection point is `OrderManager`, not `BaseStrategy.on_bar()`. Reasons:

1. `OrderManager` is the single place all order submissions happen (`buy`, `sell`, `short_sell`, `buy_to_cover`, `close_position`). No strategy bypasses it.
2. `BaseStrategy.on_bar()` has 13 different strategy implementations — hooking there requires modifying all of them, or adding abstract method boilerplate to `BaseStrategy`.
3. Orders are submitted in `OrderManager` before fill confirmation exists. The write should happen on a best-effort basis using the submitted order object, not on confirmed fill (Alpaca paper trading returns order objects immediately; fills are async).

**Hook:** Add `self.md_logger` to `OrderManager.__init__` as an optional argument defaulting to `None`. In each order method, after the `self.logger.info(f"... submitted order_id={order.id}")` line, call `self.md_logger.log_order(...)` if `md_logger` is not None. This keeps the change minimal and the logger optional.

### Where NOT to Hook

- Do not add MotherDuck writes to `BaseStrategy.on_bar()` — this is called every bar tick for every strategy, not only on trade events.
- Do not add writes to `core/scheduler.py` — the scheduler calls `on_bar` but has no access to trade data.
- Do not hook into `core/logger.py` — that is a file logger; mixing concerns creates fragility.

### Position Snapshots

Position snapshots (for the live positions Dive) cannot be captured from order submission alone, because they need the Alpaca position state. The cleanest hook is in `runner.py`'s `main()` function, after `run_cron()` returns (i.e., at end of the GitHub Actions execution). For a cron strategy that runs once and exits, `run_cron` completes one `on_bar` call and then the process exits. Add a `snapshot_positions(client, strategy_name, md_logger)` call between `run_cron(...)` and process exit. For daily strategies this means one snapshot per day.

---

## Component Boundaries

| Component | Responsibility | Calls / Called By |
|-----------|---------------|-------------------|
| `core/motherduck_logger.py` | DuckDB connection lifecycle, schema creation, writes to trades/positions/portfolio_snapshots | Called by OrderManager (trades), runner.py (positions/portfolio) |
| `core/order_manager.py` (modified) | Accepts optional `md_logger` param; calls `md_logger.log_order()` after each order submission | Called by strategies; calls md_logger |
| `runner.py` (modified) | Constructs `MotherDuckLogger`, passes to `OrderManager`; calls snapshot after execution | Entry point |
| `.github/workflows/*.yml` | Trigger `runner.py` on schedule; inject secrets; run per-account strategy batches | Calls runner.py |
| MotherDuck (storage) | Stores trades, positions, portfolio_snapshots tables in `trading` database | Written by md_logger; queried by Dives |

---

## MotherDuckLogger Design

### Connection Pattern

```python
import os
import duckdb

class MotherDuckLogger:
    def __init__(self, strategy: str):
        self.strategy = strategy
        token = os.environ["MOTHERDUCK_TOKEN"]
        self.con = duckdb.connect(f"md:trading?motherduck_token={token}")
        self._ensure_schema()

    def _ensure_schema(self):
        self.con.sql("""
            CREATE TABLE IF NOT EXISTS trades (
                id          VARCHAR DEFAULT gen_random_uuid(),
                strategy    VARCHAR NOT NULL,
                symbol      VARCHAR NOT NULL,
                side        VARCHAR NOT NULL,  -- BUY, SELL, SHORT, COVER
                qty         DOUBLE NOT NULL,
                order_id    VARCHAR,
                submitted_at TIMESTAMPTZ DEFAULT now(),
            )
        """)
        self.con.sql("""
            CREATE TABLE IF NOT EXISTS positions (
                strategy    VARCHAR NOT NULL,
                symbol      VARCHAR NOT NULL,
                qty         DOUBLE NOT NULL,
                market_value DOUBLE,
                unrealized_pl DOUBLE,
                snapshotted_at TIMESTAMPTZ DEFAULT now(),
            )
        """)
        self.con.sql("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                strategy    VARCHAR NOT NULL,
                account     VARCHAR NOT NULL,
                equity      DOUBLE,
                cash        DOUBLE,
                snapshotted_at TIMESTAMPTZ DEFAULT now(),
            )
        """)
```

**Key decisions:**
- Use `CREATE TABLE IF NOT EXISTS` so `_ensure_schema()` is idempotent — safe to call on every run without state checks.
- Use `md:trading` — one database named `trading` for all strategies, separated by the `strategy` column. Do not create per-strategy databases; cross-strategy queries (for the comparison Dive) require data in one database.
- Token via environment variable, not config parameter, so it works identically in local dev (export MOTHERDUCK_TOKEN=...) and GitHub Actions (secret injected as env var).
- Hold a single `self.con` for the lifetime of the logger instance (one per runner.py execution, which is one GitHub Actions job). Do not open/close per write.

### Write Pattern

For trade logging (individual order events — always small volume):

```python
def log_order(self, order, symbol: str, side: str, qty: float):
    try:
        self.con.execute(
            "INSERT INTO trades (strategy, symbol, side, qty, order_id) VALUES (?, ?, ?, ?, ?)",
            [self.strategy, symbol, side, qty, str(order.id) if order else None]
        )
    except Exception as e:
        # Never let MD failure break order execution
        pass  # or self.file_logger.warning(...)
```

`executemany` is acceptable here because the number of trades per strategy run is tiny (single digits to tens at most). The MotherDuck docs recommend avoiding `executemany` only for datasets over 500 rows. Individual trade inserts will never approach that.

---

## Data Flow

```
GitHub Actions trigger (cron schedule)
  └── runner.py
        ├── load .env.<account> for the account
        ├── construct MotherDuckLogger(strategy)
        │     └── connect to md:trading
        │     └── CREATE TABLE IF NOT EXISTS (idempotent)
        ├── construct OrderManager(client, logger, md_logger)
        ├── construct strategy(...)
        ├── run_cron(strategy, client, config)
        │     └── on_bar(bars)
        │           ├── strategy logic
        │           └── order_manager.buy/sell/...
        │                 ├── submit order to Alpaca
        │                 └── md_logger.log_order(order, ...)
        └── md_logger.snapshot_positions(client)
              └── get_all_positions() → INSERT INTO positions
              └── get_account() → INSERT INTO portfolio_snapshots
```

---

## GitHub Actions Workflow Structure

### Decision: Per-Account Workflows, Not Per-Strategy

There are 13 strategies across 3 accounts (stat_arb, macro_vol, stock_alpha). Strategies within an account share a `.env.<account>` file and therefore share Alpaca API keys. The natural grouping is per-account, not per-strategy.

**Approach:** One workflow file per account. Each workflow has a matrix job where the matrix values are the strategy names for that account. All matrix jobs run in parallel on the shared cron schedule for that account. This gives:
- 3 workflow files instead of 13
- New strategies added by editing one matrix list
- Secrets managed per-account (3 secret sets, matching the existing `.env.*` structure)

**Why not one workflow for all strategies with a full matrix:** Different accounts have different Alpaca keys. GitHub Actions secrets cannot be selected dynamically from a matrix value at runtime (secrets are referenced by literal name, not by variable). Per-account workflows allow `ALPACA_API_KEY_STAT_ARB` etc. to be referenced statically.

**Why not one workflow per strategy:** 13 workflow files that are 95% identical violates DRY. Changes to setup steps (checkout, python install, pip install) would require editing 13 files.

### Recommended Structure

```yaml
# .github/workflows/stat_arb.yml
name: stat_arb account strategies

on:
  schedule:
    - cron: '5 21 * * 1-5'  # 4:05 PM ET (21:05 UTC) Mon-Fri for daily strategies
  workflow_dispatch:          # manual trigger for testing

jobs:
  run-strategy:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false        # one strategy failing should not cancel others
      matrix:
        strategy: [stat_arb, stat_arb_v2, stat_arb_v3]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python runner.py --strategy ${{ matrix.strategy }} --mode paper --trigger cron
        env:
          ALPACA_API_KEY: ${{ secrets.STAT_ARB_ALPACA_KEY }}
          ALPACA_SECRET_KEY: ${{ secrets.STAT_ARB_ALPACA_SECRET }}
          MOTHERDUCK_TOKEN: ${{ secrets.MOTHERDUCK_TOKEN }}
```

The `MOTHERDUCK_TOKEN` secret is shared across all workflows (one MotherDuck account for all analytics). The Alpaca secrets are per-account.

### Strategy-to-Account Mapping for Workflows

| Workflow file | Account | Strategies in matrix | Cron |
|---------------|---------|----------------------|------|
| `stat_arb.yml` | stat_arb | stat_arb, stat_arb_v2, stat_arb_v3, market_neutral, market_neutral_v2 | 4:05 PM ET daily |
| `macro_vol.yml` | macro_vol | trend_following, trend_following_v2, regime_switching, vol_risk_premium | 4:05 PM ET daily |
| `stock_alpha.yml` | stock_alpha | multi_factor_equity, multi_factor_equity_v2, post_earnings_drift | 4:05 PM ET daily |

All strategies currently use `INTERVAL = "1d"`, so all cron schedules are the same (4:05 PM ET = 21:05 UTC on weekdays). If a strategy is added with an intraday interval, it needs its own entry in the matrix with a separate cron or workflow.

---

## MotherDuck Dives Integration

Dives are AI-generated interactive visualizations created through natural language against live MotherDuck tables. They are not programmatically created from Python — they are created manually once in the MotherDuck UI (or via Claude using the MCP server) and then persist, querying live data on each view.

**Workflow to create Dives:**
1. Python writes data to `trading.trades`, `trading.positions`, `trading.portfolio_snapshots` via `MotherDuckLogger`.
2. After data exists in those tables, open MotherDuck UI with an AI assistant connected via the MCP server.
3. Prompt: "Create a Dive showing equity curve (cumulative P&L per strategy over time from portfolio_snapshots)" — the AI generates the SQL and persists the Dive.
4. The Dive queries live tables on each open, so it updates automatically as new data is written.

**Dives to create (4 required):**
- Equity curve: cumulative P&L per strategy over time from `portfolio_snapshots`
- Trade log: all rows from `trades` joined to compute per-trade P&L (needs entry/exit correlation)
- Strategy comparison: Sharpe, drawdown, win rate aggregated from `trades` and `portfolio_snapshots`
- Live positions: current rows from `positions` with most recent `snapshotted_at`

**What "Flights" aggregation can be replaced with:** SQL views defined in the `trading` database provide the same computed metrics without any scheduled pipeline. Define views at schema creation time:

```sql
CREATE OR REPLACE VIEW daily_pnl AS
SELECT strategy, date_trunc('day', snapshotted_at) as day,
       last(equity ORDER BY snapshotted_at) - first(equity ORDER BY snapshotted_at) as pnl
FROM portfolio_snapshots
GROUP BY ALL;
```

Dives query these views directly. No scheduler needed — the view recomputes on each query against the live table.

---

## Build Order (Dependencies-First)

1. **Schema + MotherDuckLogger** (`core/motherduck_logger.py`) — everything else depends on this. Includes `_ensure_schema()`, `log_order()`, `snapshot_positions()`, `snapshot_portfolio()`. Validate by running the file standalone against a test MotherDuck database.

2. **OrderManager modification** (`core/order_manager.py`) — add optional `md_logger` param to `__init__`, call `md_logger.log_order()` in each order method. Backward-compatible: default `md_logger=None` means existing tests and usage need zero changes.

3. **runner.py modification** — construct `MotherDuckLogger`, pass to `OrderManager`, call snapshot methods after `run_cron`. Guarded by `if MOTHERDUCK_TOKEN env var is set` so it degrades gracefully if token is absent (local dev without MotherDuck).

4. **GitHub Actions workflows** (`.github/workflows/*.yml`) — three files (one per account). Requires secrets to be set in GitHub repo settings first. Validate with `workflow_dispatch` (manual trigger) before relying on cron.

5. **SQL Views in MotherDuck** — created once via MotherDuck UI or a `setup_schema.py` script after step 1 ships and data exists. `CREATE OR REPLACE VIEW` for daily_pnl, strategy_metrics, etc.

6. **Dives creation** — done manually via MotherDuck UI / MCP server after data exists in the tables (steps 1-4 must be shipping real data first).

---

## New vs Modified Files

### New Files
| File | What It Contains |
|------|-----------------|
| `core/motherduck_logger.py` | `MotherDuckLogger` class: connection, schema, log_order, snapshot_positions, snapshot_portfolio |
| `.github/workflows/stat_arb.yml` | Matrix workflow for stat_arb account strategies |
| `.github/workflows/macro_vol.yml` | Matrix workflow for macro_vol account strategies |
| `.github/workflows/stock_alpha.yml` | Matrix workflow for stock_alpha account strategies |

### Modified Files
| File | Change | Risk |
|------|--------|------|
| `core/order_manager.py` | Add `md_logger=None` param to `__init__`; call `md_logger.log_order()` in 4 order methods | Low — additive, default=None preserves all existing behavior |
| `runner.py` | Construct `MotherDuckLogger`, pass to `OrderManager`, call snapshot after run_cron | Low — wrapped in env var guard |
| `requirements.txt` | Add `duckdb>=1.5.3` | None |

### Not Modified
- `core/base_strategy.py` — no changes required
- All `strategies/*/strategy.py` — no changes required
- `core/scheduler.py` — no changes required
- `core/logger.py` — no changes required
- `core/accounts.py` — no changes required

---

## Scalability Considerations

| Concern | Current (year 1) | At 5 years |
|---------|-----------------|------------|
| Write volume | ~10-50 trades/day across all strategies | ~50-500 trades/day — still trivial for executemany |
| Query volume | Dives queries on open (user-triggered) | Same — Dives are not real-time |
| Schema changes | `CREATE TABLE IF NOT EXISTS` is additive | Use `ALTER TABLE ADD COLUMN IF NOT EXISTS` pattern for additions |
| MotherDuck cost | Negligible — tiny write volume, serverless billing | Still negligible at this trade frequency |

---

## Sources

- MotherDuck Python connection: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/connecting-to-motherduck/
- MotherDuck Python data loading: https://motherduck.com/docs/key-tasks/loading-data-into-motherduck/loading-data-md-python/
- MotherDuck Dives documentation: https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/
- MotherDuck SQL reference (confirmed "Flights" not a feature): https://motherduck.com/docs/sql-reference/motherduck-sql-reference/
- GitHub Actions matrix strategy: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow
- GitHub Actions schedule syntax: https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions
