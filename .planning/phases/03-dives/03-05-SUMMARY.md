---
phase: 03-dives
plan: 05
subsystem: ui
tags: [motherduck, dives, tsx, daily_pnl, dives-04, metrics]

requires:
  - phase: 03-dives
    provides: "dives/_conventions.tsx (N, PNL hex) + Wave 0 gate"
  - phase: 02-flights
    provides: "daily_pnl with pre-computed sharpe_7d, max_drawdown, win_count, trade_count, realized_pnl"
provides:
  - "dives/strategy-comparison.tsx (DIVES-04)"
  - "live MotherDuck Dive 'strategy-comparison'"
affects: []

tech-stack:
  added: []
  patterns:
    - "Read pre-computed metrics (AVG(sharpe_7d), MIN(max_drawdown)); never recompute in the Dive"
    - "NULLIF(SUM(trade_count),0) divide-by-zero guard; NULL-tolerant cell formatter -> '—'"

key-files:
  created: [dives/strategy-comparison.tsx]
  modified: []

key-decisions:
  - "Colored the optional total_pnl cell green/red (consistent with the other Dives)"

patterns-established:
  - "NULL-tolerant fmt() helper for pre-computed metric columns"

requirements-completed: [DIVES-04]

duration: ~6min
completed: 2026-06-03
---

# Phase 3 (Plan 05): Strategy Comparison Dive (DIVES-04)

**`dives/strategy-comparison.tsx` + live `strategy-comparison` Dive: one row per strategy from `"trading"."main"."daily_pnl"` with Sharpe 7d, max drawdown, win rate %, trade count, and total P&L — Sharpe/drawdown read (not recomputed), NULLIF-guarded win rate, NULL-tolerant cells.**

## Performance
- **Duration:** ~6 min
- **Completed:** 2026-06-03
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- `GROUP BY strategy_name ORDER BY total_pnl DESC`; `AVG(sharpe_7d)`, `MIN(max_drawdown)` read straight from the pre-computed columns (not recomputed).
- `win_rate_pct = ROUND(100.0 * SUM(win_count) / NULLIF(SUM(trade_count), 0), 1)` — divide-by-zero safe.
- NULL `sharpe_7d`/`max_drawdown` render as `"—"` via a `fmt()` guard (Flight writes NULL on insufficient history) — never NaN/crash.
- Verified via MCP `query`: SQL runs cleanly, one row per strategy (0 now — `daily_pnl` empty), no divide-by-zero.

## Task Commits
1. **Task 1: Author dives/strategy-comparison.tsx and create the live Dive via MCP** — `9d4f9fa` (feat)

## Files Created/Modified
- `dives/strategy-comparison.tsx` — DIVES-04 strategy comparison Dive

## Live Dive
- **strategy-comparison** — https://app.motherduck.com/dives/strategy-comparison-65065344-c282-4e1a-9eaa-b4a5866d1da6
- `REQUIRED_DATABASES`: not needed.
- DIVES-04 SQL row count at verification: 0 strategies (`daily_pnl` empty).
- Sharpe/drawdown read (not recomputed); NULLIF win-rate guard present.

## Decisions Made
- Colored the `total_pnl` cell green/red (optional, consistent with other Dives).

## Deviations from Plan
None — plan executed as written.

## Issues Encountered
- `trading` unshared with the org (viewable by creator; org sharing left to the user). No catalog warnings.

## Next Phase Readiness
- DIVES-04 delivered; all four Wave 2 Dives complete. Phase 3 ready for verification.

---
*Phase: 03-dives*
*Completed: 2026-06-03*
