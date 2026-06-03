---
phase: 03-dives
plan: 04
subsystem: ui
tags: [motherduck, dives, tsx, recharts, daily_pnl, dives-03, equity-curve]

requires:
  - phase: 03-dives
    provides: "dives/_conventions.tsx (N, LINE_COLORS) + Wave 0 gate"
  - phase: 02-flights
    provides: "trading.main.daily_pnl (date, strategy_name, realized_pnl) from the aggregation Flight"
provides:
  - "dives/equity-curve.tsx (DIVES-03)"
  - "live MotherDuck Dive 'equity-curve'"
affects: []

tech-stack:
  added: []
  patterns:
    - "generate_series date-spine CROSS JOIN strategies LEFT JOIN cumulative-P&L + COALESCE gap-fill"
    - "long->wide pivot in React useMemo for recharts multi-line"

key-files:
  created: [dives/equity-curve.tsx]
  modified: []

key-decisions:
  - "Omitted the optional top-5/show-all useDiveState toggle (plan marks it nice-to-have); avoids risk to the gap-free/multi-line requirements"
  - "Line type='linear' per the MotherDuck design system (guide overrides research's 'monotone')"

patterns-established:
  - "Chart Dive with per-section skeleton + empty-state guard"

requirements-completed: [DIVES-03]

duration: ~7min
completed: 2026-06-03
---

# Phase 3 (Plan 04): Equity Curve Dive (DIVES-03)

**`dives/equity-curve.tsx` + live `equity-curve` Dive: per-strategy cumulative P&L over a 90-day `generate_series` date spine (COALESCE gap-fill), pivoted long→wide in a `useMemo` and rendered as a recharts multi-line `LineChart` in a `ResponsiveContainer`.**

## Performance
- **Duration:** ~7 min
- **Completed:** 2026-06-03
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- 89-day `date_spine` (`unnest(generate_series(...))`) CROSS JOIN distinct strategies LEFT JOIN per-strategy cumulative `realized_pnl` window, `COALESCE(...,0)` → one row per (date, strategy), no time-axis holes (Pitfall 3).
- `useMemo` pivots long-format rows to wide (`byDate[date][strategy]`), returns `{ data, strategies }`; one `<Line dataKey={strategy}>` per strategy using `LINE_COLORS` (Pitfall 7).
- Verified via MCP `query`: SQL runs cleanly, **no NULL `cumulative_pnl`** (COALESCE applied); 0 rows now (empty `daily_pnl` → no strategies → empty spine), so the Dive shows "No data yet".

## Task Commits
1. **Task 1: Author dives/equity-curve.tsx and create the live Dive via MCP** — `ea6bfba` (feat)

## Files Created/Modified
- `dives/equity-curve.tsx` — DIVES-03 equity curve Dive

## Live Dive
- **equity-curve** — https://app.motherduck.com/dives/equity-curve-9af6f122-98c1-43b9-a035-712c9c89a2fa
- `REQUIRED_DATABASES`: not needed.
- DIVES-03 SQL row count at verification: 0 (date × strategy; `daily_pnl` empty).
- Optional top-5/show-all toggle: **not added** (nice-to-have only).
- Gap-fill: `COALESCE(sd.cumulative_pnl, 0)` eliminates holes.

## Decisions Made
- `type="linear"` lines per the MotherDuck design-system guide (overrides research's `monotone`).
- Skipped the optional UX toggle to keep the required gap-free/multi-line behavior simple.

## Deviations from Plan
None material — the optional toggle was explicitly optional and was omitted by design.

## Issues Encountered
- `trading` unshared with the org (viewable by creator; org sharing left to the user). No catalog warnings.

## Next Phase Readiness
- DIVES-03 delivered; 03-05 remains.

---
*Phase: 03-dives*
*Completed: 2026-06-03*
