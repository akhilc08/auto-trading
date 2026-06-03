---
phase: 02-flights
plan: 04
subsystem: aggregation-flight
tags: [flights, aggregation, motherduck, daily_pnl]
requires: []
provides:
  - "daily-pnl-aggregation live MotherDuck Flight"
  - "trading.main.daily_pnl rows (idempotent prior-day rollup)"
affects: []
tech-stack:
  added: []
  patterns:
    - "Idempotent daily rollup: INSERT ... ON CONFLICT (date,strategy_name,account_name) DO UPDATE on non-key metric columns only"
    - "sharpe_7d/max_drawdown computed in a second UPDATE pass from daily_pnl's own history (NULL on <7 days)"
key-files:
  created:
    - flights/aggregation/daily_pnl.py
    - flights/aggregation/requirements.txt
  modified: []
key-decisions:
  - "Two-pass write: (1) upsert prior-day realized_pnl/trade_count/win_count; (2) UPDATE sharpe_7d (trailing-7 mean/stddev, NULL if <7 days or zero variance) and max_drawdown (max peak-to-trough of cumulative realized_pnl over all history). Avoids needing the new row's value during its own INSERT."
  - "Self-contained single-file Flight (only duckdb) — no repo install needed, unlike the exec Flights."
requirements-completed: [AGG-01, AGG-02, AGG-03, AGG-04, AGG-05, AGG-06]
duration: "~15 min"
completed: "2026-06-03"
---

# Phase 02 Plan 04: daily-pnl-aggregation Flight Summary

Idempotent daily P&L rollup Flight on MotherDuck: aggregates the prior trading day's filled trades into per-strategy/per-account `daily_pnl` rows, re-runnable without duplication.

## What Was Built
- **`flights/aggregation/daily_pnl.py`** — `main()` connects `md:`, ensures the SCHEMA-04 `daily_pnl` table, upserts prior-day base metrics (realized_pnl/trade_count/win_count) filtered to `status='filled'`, then computes sharpe_7d + max_drawdown in a second pass.
- **`flights/aggregation/requirements.txt`** — `duckdb==1.5.2`.
- **Live Flight `daily-pnl-aggregation`** (id 8d6a519b-…): cron `0 22 * * 1-5` (6 PM ET summer), token `MotherDuck Extension`.

## Verification (live)
- Runs #1/#2: clean **0 rows** (no filled trades for prior day) — correct, no error.
- Synthetic idempotency test (2 fake filled trades for prior day, +50 and −20, then removed):
  - daily_pnl row: realized_pnl=**30.00**, trade_count=**2**, win_count=**1**, sharpe_7d=**NULL** (insufficient history, not a constant), max_drawdown=**0** — all correct (AGG-01/02).
  - Re-run (run #4): still exactly **1 row**, identical values — idempotent (AGG-05). No duplication.
  - Synthetic trades + daily_pnl row deleted; tables clean.

## Deviations from Plan
**[Rule 1 — bug fix] DST cron inversion.** The plan/REQUIREMENTS AGG-03 stated summer = `"0 23 * * 1-5"` / winter = `"0 22 * * 1-5"`. That is inverted: 18:00 EDT (UTC-4) = 22:00 UTC, so summer is `"0 22"` and winter is `"0 23"` (matching the exec-flight cron convention, which the plan had correct). Deployed with the correct summer value `0 22 * * 1-5`; corrected the docstring.

**Total deviations:** 1 (cron DST fix). **Impact:** Flight fires at the intended 6 PM ET; the original value would have fired at 7 PM ET in summer (still harmless, but not as specified).

## Self-Check: PASSED
- key-files exist; commits present; Task 1 acceptance verify PASS; live idempotency verified with synthetic data then cleaned up.

## Next
Independent of the exec Flights. Phase 3 (Dives) equity-curve/strategy-comparison views read this `daily_pnl` table.
