---
phase: 03-dives
plan: 02
subsystem: ui
tags: [motherduck, dives, tsx, useDiveState, trades, dives-01]

requires:
  - phase: 03-dives
    provides: "dives/_conventions.tsx (N, PNL hex, STRATEGIES allow-list) + Wave 0 gate"
  - phase: 01-schema-logger-integration
    provides: "trading.main.trades schema (symbol, side, qty, submitted_at, filled_avg_price, pnl, strategy_name)"
provides:
  - "dives/trade-log.tsx (DIVES-01)"
  - "live MotherDuck Dive 'trade-log'"
affects: []

tech-stack:
  added: []
  patterns:
    - "useDiveState strategy filter validated against the closed STRATEGIES allow-list before SQL interpolation (T-3-01)"

key-files:
  created: [dives/trade-log.tsx]
  modified: []

key-decisions:
  - "Filter validates strategy against STRATEGIES.includes(...) before building the WHERE clause; non-allow-list values fall back to no filter"

patterns-established:
  - "Color-coded pnl cell via inline style {{ color: N(r.pnl) >= 0 ? PNL_GREEN : PNL_RED }}"

requirements-completed: [DIVES-01]

duration: ~6min
completed: 2026-06-03
---

# Phase 3 (Plan 02): Trade Log Dive (DIVES-01)

**`dives/trade-log.tsx` + live `trade-log` Dive: 90-day trades from `"trading"."main"."trades"`, filterable by a closed-allow-list strategy dropdown (useDiveState), with green/red color-coded P&L and an empty-state guard.**

## Performance
- **Duration:** ~6 min
- **Completed:** 2026-06-03
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- `useDiveState("strategy", "all")` dropdown built only from the 12-entry `STRATEGIES` allow-list + "all".
- Filter value validated with `STRATEGIES.includes(strategy)` before interpolation (T-3-01 mitigation); tampered/unknown values fall back to no filter.
- DIVES-01 SQL (symbol, side, qty, submitted_at, filled_avg_price, pnl, strategy_name; 90-day window; `LIMIT 500`) verified to execute cleanly via MCP `query` (0 rows — empty trades table).
- pnl cell color-coded `#2d7a00`/`#bc1200` via inline style; `Array.isArray(data)` guard; "No data yet" empty state.

## Task Commits
1. **Task 1: Author dives/trade-log.tsx and create the live Dive via MCP** — `00d5809` (feat)

## Files Created/Modified
- `dives/trade-log.tsx` — DIVES-01 trade log Dive

## Live Dive
- **trade-log** — https://app.motherduck.com/dives/trade-log-5a2308d1-b2ac-43fa-9b08-1dbe2d826a92
- `REQUIRED_DATABASES`: not needed.
- DIVES-01 SQL row count at verification: 0 (trades table empty).

## Decisions Made
- Allow-list validation done in JS before SQL build (defense-in-depth on top of the hardcoded dropdown options).

## Deviations from Plan
None — plan executed as written.

## Issues Encountered
- `save_dive` returned a benign `database_warnings: ["Database 'e' not found"]` — a false positive where the catalog scanner misreads the `e.target.value` event-handler access as a table reference. The real query references only `"trading"."main"."trades"` (correctly listed in `unshared_databases`). Dive saved and is viewable; no action needed.
- `trading` is unshared with the org — Dive is viewable by the creator; org sharing not performed (left to the user).

## Post-Review Fix (WR-04)
Code review confirmed the T-3-01 allow-list mitigation is sound, and recommended defense-in-depth so safety is local to the interpolation site rather than dependent on allow-list contents. **Added** a `/^[a-z0-9_]+$/` identifier assertion alongside `STRATEGIES.includes(strategy)` before interpolation. Committed in `f6a149b`; live Dive updated in place via `update_dive`. (WR-03 — show "—" for NULL filled_avg_price/pnl — left as an advisory follow-up, not applied.)

## Next Phase Readiness
- DIVES-01 delivered; remaining Wave 2 Dives (03-03/04/05) are independent.

---
*Phase: 03-dives*
*Completed: 2026-06-03*
