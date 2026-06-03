# Roadmap: auto-trading — v1.0 MotherDuck Cloud Deployment

## Overview

This milestone takes a working Alpaca-based multi-strategy trading framework and adds a full cloud execution and observability layer using MotherDuck exclusively. Schema and logger land first, then wire into existing order flow, then Execution Flights run strategies on MotherDuck compute (reading Alpaca credentials from DuckDB secrets), then an Aggregation Flight computes daily P&L, and finally Dives make everything visible. No GitHub Actions. No external servers.

## Phases

- [ ] **Phase 1: Schema & Logger** - Create MotherDuck tables and the Python logger class that writes to them
- [ ] **Phase 2: Integration** - Wire the logger into OrderManager and runner.py without touching any strategy file
- [ ] **Phase 3: Execution Flights** - Three Flights (one per account) with bundled strategy code and Alpaca secrets from DuckDB
- [ ] **Phase 4: Aggregation Flight** - Daily P&L aggregation Flight that runs on MotherDuck compute at 6 PM ET
- [ ] **Phase 5: Dives** - Four interactive visualizations querying live trade and aggregation data

## Phase Details

### Phase 1: Schema & Logger
**Goal**: The MotherDuck schema exists and the logger class can write trades, positions, and portfolio snapshots to it
**Depends on**: Nothing (first phase)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, SCHEMA-09, SCHEMA-10
**Success Criteria**:
  1. Running `core/motherduck_logger.py` against a live token creates all four tables without error
  2. `log_order()` inserts a row; duplicate `order_id` inserts nothing (`ON CONFLICT DO NOTHING`)
  3. `update_fill()` writes `filled_at`, `filled_avg_price`, and `pnl` onto the trade row
  4. Without `MOTHERDUCK_TOKEN` set, local execution continues with no exception
**Plans**: TBD

### Phase 2: Integration
**Goal**: Every order submitted by any of the 13 strategies is logged to MotherDuck, and position/portfolio snapshots are written after each cron run — without modifying any strategy file
**Depends on**: Phase 1
**Requirements**: INTEG-01, INTEG-02, INTEG-03, INTEG-04, INTEG-05, INTEG-06
**Success Criteria**:
  1. Existing `OrderManager` callers with no `md_logger` argument continue unchanged
  2. Running `runner.py` with `MOTHERDUCK_TOKEN` set produces a new `trades` row per submitted order
  3. After `run_cron()`, `positions` and `portfolio_snapshots` each gain a timestamped snapshot row
  4. No file under `strategies/` is modified
**Plans**: TBD

### Phase 3: Execution Flights
**Goal**: Three MotherDuck Flights execute all strategies on their cron schedules, reading Alpaca credentials from DuckDB secrets and writing results to MotherDuck
**Depends on**: Phase 2
**Requirements**: SECRETS-01, SECRETS-02, SECRETS-03, EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08
**Success Criteria**:
  1. Alpaca credentials for all three accounts exist as DuckDB secrets in MotherDuck — no plaintext credentials anywhere in Flight source or config
  2. Manually triggering any execution Flight via `run_flight` produces `trades`, `positions`, and `portfolio_snapshots` rows in MotherDuck
  3. Triggering a Flight when the market is closed produces no orders and exits cleanly
  4. One strategy failing within a Flight does not prevent other strategies in the same Flight from running
**Plans**: TBD

### Phase 4: Aggregation Flight
**Goal**: A MotherDuck Flight aggregates the previous trading day's filled trades into `daily_pnl` every weekday at 6 PM ET, and re-running it produces the same result
**Depends on**: Phase 3
**Requirements**: AGG-01, AGG-02, AGG-03, AGG-04, AGG-05, AGG-06
**Success Criteria**:
  1. Manually triggering `run_flight` on `daily-pnl-aggregation` produces rows in `daily_pnl`
  2. Running the Flight twice produces the same row count (idempotent via `ON CONFLICT DO UPDATE`)
  3. Only `status = 'filled'` trades appear in `daily_pnl`
  4. Flight uses pinned `duckdb==1.5.2` and a service account token
**Plans**: TBD

### Phase 5: Dives
**Goal**: Four Dives in MotherDuck make all trade, position, and performance data visible and interactive
**Depends on**: Phase 4
**Requirements**: DIVES-01, DIVES-02, DIVES-03, DIVES-04
**Success Criteria**:
  1. Trade log Dive shows 90-day history filterable by strategy
  2. Live positions Dive shows open positions with green/red unrealized P&L
  3. Equity curve Dive shows per-strategy cumulative P&L with no time-series gaps
  4. Strategy comparison Dive shows Sharpe, drawdown, win rate, trade count, total P&L for all strategies
**UI hint**: yes
**Plans**: TBD

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 (strict dependencies)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema & Logger | 0/? | Not started | - |
| 2. Integration | 0/? | Not started | - |
| 3. Execution Flights | 0/? | Not started | - |
| 4. Aggregation Flight | 0/? | Not started | - |
| 5. Dives | 0/? | Not started | - |
