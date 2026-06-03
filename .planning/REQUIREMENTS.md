# Requirements: auto-trading

**Defined:** 2026-06-03
**Milestone:** v1.0 — MotherDuck Cloud Deployment
**Core Value:** Strategies execute reliably on schedule and every trade is observable — visible in MotherDuck with accurate P&L, position state, and cross-strategy comparison.

## v1.0 Requirements

### Schema & Logger

- [ ] **SCHEMA-01**: System creates `trades` table in MotherDuck with columns: `order_id` (PK), `strategy_name`, `account_name`, `symbol`, `side`, `qty`, `submitted_at` (TIMESTAMPTZ), `filled_at` (TIMESTAMPTZ), `filled_avg_price`, `pnl`, `status`
- [ ] **SCHEMA-02**: System creates `positions` table with columns: `snapshot_at` (TIMESTAMPTZ), `strategy_name`, `account_name`, `symbol`, `qty`, `avg_entry_price`, `current_price`, `unrealized_pnl`
- [ ] **SCHEMA-03**: System creates `portfolio_snapshots` table with columns: `snapshot_at` (TIMESTAMPTZ), `strategy_name`, `account_name`, `equity`, `cash`, `buying_power`
- [ ] **SCHEMA-04**: System creates `daily_pnl` table with columns: `date` + `strategy_name` + `account_name` (composite PK), `realized_pnl`, `trade_count`, `win_count`, `sharpe_7d`, `max_drawdown`
- [ ] **SCHEMA-05**: `MotherDuckLogger` connects via service account token from `MOTHERDUCK_TOKEN` env var and runs `CREATE TABLE IF NOT EXISTS` on startup for all tables
- [ ] **SCHEMA-06**: `MotherDuckLogger.log_order()` writes to `trades` using `INSERT ... ON CONFLICT (order_id) DO NOTHING`
- [ ] **SCHEMA-07**: `MotherDuckLogger.update_fill()` updates a submitted trade row with `filled_at`, `filled_avg_price`, and computed `pnl` once Alpaca confirms the fill
- [ ] **SCHEMA-08**: `MotherDuckLogger.snapshot_positions()` writes current open positions from Alpaca to `positions` table
- [ ] **SCHEMA-09**: `MotherDuckLogger.snapshot_portfolio()` writes account equity/cash from Alpaca to `portfolio_snapshots` table
- [ ] **SCHEMA-10**: Logger degrades gracefully when `MOTHERDUCK_TOKEN` is absent — local runs continue working normally

### Integration

- [ ] **INTEG-01**: `OrderManager` accepts optional `md_logger=None` parameter — all existing callers continue working without changes
- [ ] **INTEG-02**: `OrderManager` calls `md_logger.log_order()` after each order submission across all 5 order methods (buy, sell, short_sell, buy_to_cover, close_position)
- [ ] **INTEG-03**: `runner.py` constructs `MotherDuckLogger` when `MOTHERDUCK_TOKEN` is present and passes it to `OrderManager`
- [ ] **INTEG-04**: `runner.py` calls `md_logger.snapshot_positions()` and `md_logger.snapshot_portfolio()` after `run_cron()` returns
- [ ] **INTEG-05**: `runner.py` polls Alpaca for fill confirmation after `run_cron()` and calls `md_logger.update_fill()` with `filled_at`, `filled_avg_price`, and computed `pnl`
- [ ] **INTEG-06**: No strategy files (`strategies/*/strategy.py`) are modified — integration is entirely within `core/`

### Secrets

- [ ] **SECRETS-01**: Alpaca API key and secret for each account (`stat_arb`, `macro_vol`, `trend_following`) are stored as DuckDB secrets in MotherDuck using `CREATE OR REPLACE SECRET`
- [ ] **SECRETS-02**: Execution Flights read Alpaca credentials from MotherDuck secrets at runtime — no credentials in Flight `config` or `source_code`
- [ ] **SECRETS-03**: Secrets are scoped per account so each Flight only reads the credentials it needs

### Execution Flights

- [ ] **EXEC-01**: A MotherDuck Flight named `exec-stat-arb` runs the stat_arb account strategies (stat_arb, stat_arb_v2, stat_arb_v3, market_neutral, market_neutral_v2) with their strategy logic bundled in the Flight source
- [ ] **EXEC-02**: A MotherDuck Flight named `exec-macro-vol` runs the macro_vol account strategies (vol_risk_premium) with strategy logic bundled in the Flight source
- [ ] **EXEC-03**: A MotherDuck Flight named `exec-trend-following` runs the trend_following account strategies (trend_following, trend_following_v2, multi_factor_equity, multi_factor_equity_v2, regime_switching, post_earnings_drift, rl_alpha, deep_learning, alt_data_fusion) with strategy logic bundled in the Flight source
- [ ] **EXEC-04**: Each execution Flight reads Alpaca credentials from MotherDuck secrets and connects to the Alpaca API before executing strategies
- [ ] **EXEC-05**: Each execution Flight connects to MotherDuck via `duckdb.connect("md:")` and writes trades, positions, and portfolio snapshots using `MotherDuckLogger` logic (bundled inline)
- [ ] **EXEC-06**: Each execution Flight is scheduled at the appropriate market-hours cron (UTC) for its account's strategies
- [ ] **EXEC-07**: Execution Flights call `alpaca.get_clock().is_open` as a market-hours guard and exit cleanly when the market is closed
- [ ] **EXEC-08**: Execution Flights use `duckdb==1.5.2` and `alpaca-trade-api` pinned in `requirements_txt`

### Aggregation Flight

- [ ] **AGG-01**: A MotherDuck Flight named `daily-pnl-aggregation` reads `trades` and writes aggregated rows to `daily_pnl`
- [ ] **AGG-02**: Flight aggregates only `WHERE status = 'filled'` trades for the prior trading day
- [ ] **AGG-03**: Flight is scheduled at 6 PM ET Mon–Fri (`"0 23 * * 1-5"` UTC summer / `"0 22 * * 1-5"` winter)
- [ ] **AGG-04**: Flight uses `duckdb==1.5.2` pinned in `requirements_txt`
- [ ] **AGG-05**: Flight aggregation is idempotent — re-running on the same date overwrites via `ON CONFLICT (date, strategy_name, account_name) DO UPDATE`
- [ ] **AGG-06**: Flight uses a service account token via `access_token_name`

### Dives

- [ ] **DIVES-01**: Trade log Dive displays all trades with symbol, side, qty, submitted_at, filled_avg_price, pnl — default filter: last 90 days, filterable by strategy via `useDiveState`
- [ ] **DIVES-02**: Live positions Dive displays current open positions with unrealized P&L, color-coded green (`#2d7a00`) / red (`#bc1200`) — queries latest `positions` snapshot per strategy
- [ ] **DIVES-03**: Equity curve Dive displays cumulative P&L over time per strategy as a line chart — queries `daily_pnl` with time-series gap filling via `generate_series` LEFT JOIN, 90-day default window
- [ ] **DIVES-04**: Strategy comparison Dive displays Sharpe 7d, max drawdown, win rate %, trade count, and total P&L in a table for all strategies side-by-side

## Future Requirements

### v1.1 Candidates

- **SCHEMA-F01**: Data freshness monitoring — alert when `portfolio_snapshots` has no rows for the last trading day
- **DIVES-F01**: Per-account equity curve filter (schema already supports it via `account_name`)
- **DIVES-F02**: Win rate by symbol breakdown
- **DIVES-F03**: Strategy correlation heatmap
- **DIVES-F04**: Drawdown recovery chart

## Out of Scope

| Feature | Reason |
|---------|--------|
| GitHub Actions for execution | Replaced entirely by MotherDuck Flights |
| Alpaca keys in Flight config | Flight config is unencrypted — keys stored as DuckDB secrets only |
| Real-time streaming dashboards | Dives refresh on Flight schedule; streaming adds infra |
| Strategy logic rewrite as SQL | Alpaca order execution requires Python |
| Custom dashboard server (Grafana, Metabase) | Dives are the built-in solution |
| Modifying any strategy file | Integration is entirely within `core/` |

## Traceability

| REQ-ID | Phase |
|--------|-------|
| SCHEMA-01 | Phase 1 |
| SCHEMA-02 | Phase 1 |
| SCHEMA-03 | Phase 1 |
| SCHEMA-04 | Phase 1 |
| SCHEMA-05 | Phase 1 |
| SCHEMA-06 | Phase 1 |
| SCHEMA-07 | Phase 1 |
| SCHEMA-08 | Phase 1 |
| SCHEMA-09 | Phase 1 |
| SCHEMA-10 | Phase 1 |
| INTEG-01 | Phase 1 |
| INTEG-02 | Phase 1 |
| INTEG-03 | Phase 1 |
| INTEG-04 | Phase 1 |
| INTEG-05 | Phase 1 |
| INTEG-06 | Phase 1 |
| SECRETS-01 | Phase 2 |
| SECRETS-02 | Phase 2 |
| SECRETS-03 | Phase 2 |
| EXEC-01 | Phase 2 |
| EXEC-02 | Phase 2 |
| EXEC-03 | Phase 2 |
| EXEC-04 | Phase 2 |
| EXEC-05 | Phase 2 |
| EXEC-06 | Phase 2 |
| EXEC-07 | Phase 2 |
| EXEC-08 | Phase 2 |
| AGG-01 | Phase 2 |
| AGG-02 | Phase 2 |
| AGG-03 | Phase 2 |
| AGG-04 | Phase 2 |
| AGG-05 | Phase 2 |
| AGG-06 | Phase 2 |
| DIVES-01 | Phase 3 |
| DIVES-02 | Phase 3 |
| DIVES-03 | Phase 3 |
| DIVES-04 | Phase 3 |
