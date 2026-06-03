# auto-trading

## What This Is

A multi-strategy algorithmic trading framework using Alpaca Markets. Strategies live under `strategies/`, each implementing `BaseStrategy`. Shared infrastructure (Alpaca client, order management, scheduling, logging) lives in `core/`. In this milestone, strategy execution moves to GitHub Actions and all trade/position data flows through MotherDuck for analytics and visualization.

## Core Value

Strategies execute reliably on schedule and every trade is observable — visible in MotherDuck with accurate P&L, position state, and cross-strategy comparison.

## Current Milestone: v1.0 MotherDuck Cloud Deployment

**Goal:** Move strategy execution to GitHub Actions and route all trade/position data through MotherDuck for analytics and visualization via Dives.

**Target features:**
- MotherDuck schema + logging layer in `core/` (trades, positions, portfolio snapshots)
- GitHub Actions workflows for scheduled strategy execution
- MotherDuck Flights for daily aggregations (P&L, drawdown, strategy metrics)
- MotherDuck Dives: equity curve, trade log, strategy comparison, live positions

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ Multi-strategy plugin architecture (`BaseStrategy` + per-strategy folder)
- ✓ Alpaca client wrapper with paper/live mode switching
- ✓ Order manager (buy/sell/close helpers)
- ✓ Cron and stream execution modes via `runner.py`
- ✓ Per-strategy file logging (`logs/<strategy>/YYYY-MM-DD.log`)
- ✓ 13+ strategies implemented (trend_following, stat_arb, vol_risk_premium, regime_switching, etc.)
- ✓ Per-strategy backtesting scripts
- ✓ Multi-account routing via `.env.<account>` files

### Active

<!-- Current scope. Building toward these. -->

- [ ] MotherDuck schema: trades, positions, portfolio_snapshots tables
- [ ] `core/motherduck_logger.py`: writes trade fills and position snapshots to MotherDuck
- [ ] GitHub Actions workflow: runs each active strategy on its configured cron schedule
- [ ] Secrets management: Alpaca keys + MotherDuck token in GH Actions secrets
- [ ] MotherDuck Flights: daily P&L aggregation, drawdown, strategy metrics
- [ ] MotherDuck Dives: equity curve (P&L over time per strategy)
- [ ] MotherDuck Dives: trade log table (all trades with entry/exit/P&L)
- [ ] MotherDuck Dives: strategy comparison dashboard (Sharpe, drawdown, win rate)
- [ ] MotherDuck Dives: live positions view (open positions with unrealized P&L)

### Out of Scope

- Dedicated server or container deployment — GitHub Actions handles execution at no cost
- Real-time streaming dashboards — Dives refresh on Flight schedule, not live
- Strategy logic rewrite as SQL — Alpaca order execution requires Python

## Context

- Python 3.x, `alpaca-trade-api` / Alpaca SDK
- 13+ strategies: `trend_following`, `trend_following_v2`, `stat_arb`, `stat_arb_v2`, `stat_arb_v3`, `vol_risk_premium`, `regime_switching`, `multi_factor_equity`, `multi_factor_equity_v2`, `post_earnings_drift`, `rl_alpha`, `deep_learning`, `alt_data_fusion`
- Each strategy has `config.py` (SYMBOLS, INTERVAL, TRADE_OUTSIDE_HOURS) and `strategy.py`
- Multi-account routing: `core/accounts.py` maps strategies to `.env.<account>` files
- MotherDuck = DuckDB in the cloud; Flights = scheduled SQL pipelines; Dives = notebook-style visualizations
- GitHub Actions free tier supports ~2000 min/month on public repos, unlimited on private with billing

## Constraints

- **Execution**: No new servers — GitHub Actions is the only execution environment
- **Order execution**: Alpaca API calls must happen in Python (cannot be replaced by SQL in Flights)
- **Secrets**: Alpaca API keys and MotherDuck token must live in GitHub Actions secrets, never committed
- **MotherDuck**: DuckDB SQL dialect; use `motherduck_token` for auth; write via `duckdb` Python package

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GitHub Actions for execution | No server overhead, free tier, native secrets management | — Pending |
| Python writes to MotherDuck, Flights aggregate | Alpaca API can't be called from SQL; Flights best for analytics layer | — Pending |
| MotherDuck Dives for visualization | Built-in MotherDuck UI, no separate dashboard tool needed | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-02 after milestone v1.0 start*
