# Roadmap: auto-trading — v1.0 MotherDuck Cloud Deployment

## Overview

Three phases: get data flowing into MotherDuck, move execution to Flights, then visualize with Dives.

## Phases

- [x] **Phase 1: Schema, Logger & Integration** - Tables, logger class, wired into OrderManager and runner.py (completed 2026-06-03)
- [x] **Phase 2: Flights** - DuckDB secrets for Alpaca keys, 3 execution Flights + 1 aggregation Flight (completed 2026-06-03)
- [ ] **Phase 3: Dives** - Four interactive visualizations over live trade and performance data

## Phase Details

### Phase 1: Schema, Logger & Integration

**Goal**: MotherDuck tables exist, every order from every strategy is logged, and position/portfolio snapshots are written after each run — without touching any strategy file
**Depends on**: Nothing (first phase)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, SCHEMA-09, SCHEMA-10, INTEG-01, INTEG-02, INTEG-03, INTEG-04, INTEG-05, INTEG-06
**Success Criteria**:

  1. Running `runner.py` with `MOTHERDUCK_TOKEN` set produces rows in `trades`, `positions`, and `portfolio_snapshots`
  2. Submitting the same order twice results in one row, not two (`ON CONFLICT DO NOTHING`)
  3. Running without `MOTHERDUCK_TOKEN` works exactly as before — no exception, no change in behavior
  4. No file under `strategies/` is modified**Plans**: 2 plans

**Wave 1**

  - [x] 01-01-PLAN.md — MotherDuckLogger class + 4-table schema + duckdb pin (SCHEMA-01..10)

**Wave 2** *(blocked on Wave 1 completion)*

  - [x] 01-02-PLAN.md — Wire logger into OrderManager + runner.py snapshots/fill-poll (INTEG-01..06)

### Phase 2: Flights

**Goal**: All strategy execution and daily aggregation runs on MotherDuck compute — no local runner, no GitHub Actions
**Depends on**: Phase 1
**Requirements**: SECRETS-01, SECRETS-02, SECRETS-03, EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08, AGG-01, AGG-02, AGG-03, AGG-04, AGG-05, AGG-06
**Success Criteria**:

  1. Alpaca credentials exist as DuckDB secrets — no plaintext credentials in any Flight source or config
  2. Manually triggering any execution Flight produces `trades`, `positions`, and `portfolio_snapshots` rows
  3. Triggering an execution Flight when the market is closed exits cleanly with no orders
  4. Manually triggering the aggregation Flight produces `daily_pnl` rows; re-running it produces the same count

**Plans**: TBD

### Phase 3: Dives

**Goal**: Four Dives in MotherDuck make all trade, position, and performance data visible and interactive
**Depends on**: Phase 2
**Requirements**: DIVES-01, DIVES-02, DIVES-03, DIVES-04
**Success Criteria**:

  1. Trade log Dive shows 90-day history filterable by strategy
  2. Live positions Dive shows open positions with green/red unrealized P&L
  3. Equity curve Dive shows per-strategy cumulative P&L with no time-series gaps
  4. Strategy comparison Dive shows Sharpe, drawdown, win rate, trade count, total P&L for all strategies

**UI hint**: yes
**Plans**: 5 plans

  - [ ] 03-01-PLAN.md — Shared conventions, dives/ dir, STRATEGIES allow-list, SQL pre-flight + MCP Wave 0 gate (DIVES-01..04)
  - [ ] 03-02-PLAN.md — Trade log Dive: 90-day trades, useDiveState strategy filter, color-coded pnl (DIVES-01)
  - [ ] 03-03-PLAN.md — Live positions Dive: latest snapshot per strategy, green/red unrealized P&L (DIVES-02)
  - [ ] 03-04-PLAN.md — Equity curve Dive: generate_series gap-fill, recharts multi-line (DIVES-03)
  - [ ] 03-05-PLAN.md — Strategy comparison Dive: Sharpe/drawdown/win-rate/count/total-P&L table (DIVES-04)

## Progress

**Execution Order:** 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema, Logger & Integration | 2/2 | Complete    | 2026-06-03 |
| 2. Flights | 4/4 | Complete    | 2026-06-03 |
| 3. Dives | 0/5 | Not started | - |
