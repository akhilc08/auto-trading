---
phase: 03-dives
plan: 03
subsystem: ui
tags: [motherduck, dives, tsx, positions, dives-02]

requires:
  - phase: 03-dives
    provides: "dives/_conventions.tsx (N, PNL hex) + Wave 0 gate"
  - phase: 01-schema-logger-integration
    provides: "trading.main.positions schema (snapshot_at, strategy_name, symbol, qty, avg_entry_price, current_price, unrealized_pnl)"
provides:
  - "dives/live-positions.tsx (DIVES-02)"
  - "live MotherDuck Dive 'live-positions'"
affects: []

tech-stack:
  added: []
  patterns:
    - "Latest-snapshot-per-strategy via MAX(snapshot_at) CTE join (no user input — static SQL)"

key-files:
  created: [dives/live-positions.tsx]
  modified: []

key-decisions:
  - "Used the table column unrealized_pnl (not Alpaca's unrealized_pl)"

patterns-established:
  - "Static read-only Dive (no useDiveState) with color-coded unrealized P&L"

requirements-completed: [DIVES-02]

duration: ~5min
completed: 2026-06-03
---

# Phase 3 (Plan 03): Live Positions Dive (DIVES-02)

**`dives/live-positions.tsx` + live `live-positions` Dive: latest positions snapshot per strategy from `"trading"."main"."positions"` (MAX(snapshot_at) CTE join), with green/red color-coded unrealized P&L and an empty-state guard.**

## Performance
- **Duration:** ~5 min
- **Completed:** 2026-06-03
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- `latest_snapshot` CTE picks `MAX(snapshot_at)` per `strategy_name`, joined back to `positions` on `(strategy_name, snapshot_at)` — only the latest snapshot per strategy appears.
- SELECT symbol, strategy_name, qty, avg_entry_price, current_price, `unrealized_pnl` (the table column), snapshot_at; verified to run cleanly via MCP `query` (0 rows — empty positions table).
- `unrealized_pnl` cell color-coded `#2d7a00`/`#bc1200` via inline style; `Array.isArray(data)` guard; "No data yet" empty state.

## Task Commits
1. **Task 1: Author dives/live-positions.tsx and create the live Dive via MCP** — `c62f951` (feat)

## Files Created/Modified
- `dives/live-positions.tsx` — DIVES-02 live positions Dive

## Live Dive
- **live-positions** — https://app.motherduck.com/dives/live-positions-93f72573-e3a7-4d08-b5ca-6521ee3481fb
- `REQUIRED_DATABASES`: not needed.
- DIVES-02 SQL row count at verification: 0 (positions table empty).
- Color coding uses exact hex `#2d7a00` (positive) / `#bc1200` (negative).

## Decisions Made
None beyond following the plan/research SQL.

## Deviations from Plan
None — plan executed as written.

## Issues Encountered
- `trading` unshared with the org (viewable by creator; org sharing left to the user). No catalog warnings this time (no event handlers).

## Next Phase Readiness
- DIVES-02 delivered; 03-04/05 remain (independent).

---
*Phase: 03-dives*
*Completed: 2026-06-03*
