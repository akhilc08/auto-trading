---
status: partial
phase: 03-dives
source: [03-VERIFICATION.md]
started: 2026-06-03
updated: 2026-06-03
---

## Current Test

[awaiting human testing — requires non-empty trades/positions/daily_pnl tables, i.e. after live trading has logged data]

## Tests

### 1. Trade log dropdown filters rows (DIVES-01)
expected: Open the `trade-log` Dive; the table shows the last 90 days of trades. Changing the strategy dropdown changes the visible row set (only the selected strategy's trades appear; "All strategies" shows all).
result: [pending]

### 2. Live positions P&L color coding (DIVES-02)
expected: Open the `live-positions` Dive; positive `unrealized_pnl` cells render green (#2d7a00) and negative render red (#bc1200); only the latest snapshot per strategy appears.
result: [pending]

### 3. Equity curve has no time-series gaps (DIVES-03)
expected: Open the `equity-curve` Dive; one line per strategy, continuous across no-trade days (weekends/holidays) — a strategy with no trades on a day shows a flat carried-forward line, NOT a drop to $0 and NOT a hole.
result: [pending]

### 4. Strategy comparison metrics match SQL (DIVES-04)
expected: Open the `strategy-comparison` Dive; every strategy with daily_pnl rows appears with Sharpe 7d, max drawdown, win rate %, trade count, and total P&L; values cross-check against the raw SQL; NULL Sharpe/drawdown render as "—".
result: [pending]

### 5. Empty-state renders cleanly (DIVES-01..04)
expected: With empty tables, each Dive shows "No data yet — run a strategy to populate." with no crash or SQL/runtime error. (Currently verifiable now, since tables are empty.)
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
