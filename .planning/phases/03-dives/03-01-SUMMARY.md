---
phase: 03-dives
plan: 01
subsystem: ui
tags: [motherduck, dives, tsx, react, recharts, sql]

requires:
  - phase: 01-schema-logger-integration
    provides: "trading.main.trades/positions/daily_pnl table schema the Dives query"
  - phase: 02-flights
    provides: "daily_pnl aggregation (sharpe_7d, max_drawdown, win_count) the Dives read"
provides:
  - "dives/ directory with shared authoring conventions reference"
  - "STRATEGIES closed allow-list (mirror of core/accounts.py) — SQL-injection mitigation for DIVES-01"
  - "Color/helper/empty-state/table-name conventions fixed once for Wave 2 Dive authors"
  - "Wave 0 gate result: MCP reachable, all four tables resolve, REQUIRED_DATABASES not needed"
affects: [03-02, 03-03, 03-04, 03-05]

tech-stack:
  added: ["@motherduck/react-sql-query (runtime-provided)", "recharts (runtime-provided)"]
  patterns:
    - "Dive = committed dives/*.tsx file AND live Dive via MCP save_dive"
    - "Closed allow-list filter (no raw interpolation) for any user-controlled SQL value"
    - "N() BigInt guard + Array.isArray(data) rows guard + 'No data yet' empty state"

key-files:
  created:
    - dives/_conventions.tsx
    - dives/README.md
  modified: []

key-decisions:
  - "STRATEGIES = the 12 strategies in core/accounts.py _ACCOUNT_STRATEGIES (authoritative live set), NOT the 13 in research — rl_alpha/deep_learning/alt_data_fusion are unregistered and don't log trades"
  - "Omit REQUIRED_DATABASES for MCP-created Dives — creator owns trading DB (confirmed by Dive guide + Wave 0 gate)"
  - "save_dive is the create operation (no separate create_dive tool surfaced); returns a clickable Dive URL"

patterns-established:
  - "Conventions reference file copied (not imported) into each Dive — runtime has no cross-file imports"
  - "Inline style={{}} for hex colors; Tailwind bracket syntax forbidden (fails silently)"

requirements-completed: [DIVES-01, DIVES-02, DIVES-03, DIVES-04]

duration: ~10min
completed: 2026-06-03
---

# Phase 3 (Plan 01): Dives Foundation Summary

**Shared `dives/_conventions.tsx` (N() helper, PNL_GREEN/PNL_RED, LINE_COLORS, the injection-safe STRATEGIES allow-list, empty-state + table-name rules) and `README.md` deliverable model, with the Wave 0 MCP/SQL pre-flight gate confirmed green against the live `trading` DB.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-06-03
- **Tasks:** 2 (1 auto + 1 Wave 0 human-verify gate)
- **Files created:** 2

## Accomplishments
- `dives/_conventions.tsx`: `N()`, `PNL_GREEN=#2d7a00`, `PNL_RED=#bc1200`, 14-entry `LINE_COLORS`, the 12-strategy `STRATEGIES` closed allow-list (mirror of `core/accounts.py`), the `Array.isArray(data)` rows guard, the `"No data yet — run a strategy to populate."` empty state, and the fully-qualified double-quoted table-name rule.
- `dives/README.md`: deliverable model (committed `.tsx` + live Dive via MCP), file→Dive map, full SQL pre-flight block, and the REQUIRED_DATABASES fallback decision.
- **Wave 0 gate (Task 2):** MCP `query` reachable; `trades`/`positions`/`daily_pnl` all resolve (0 rows each — empty as expected, Phases 1/2 have not logged live trades); column schema confirmed to match every Dive's SQL; `save_dive` available; REQUIRED_DATABASES not needed.

## Task Commits

1. **Task 1: Create dives/ directory with shared conventions and the strategy allow-list** — `823a483` (feat)
2. **Task 2: Wave 0 gate (MCP reachability + SQL pre-flight)** — no file (validation gate); result recorded in README.md and this summary

## Files Created/Modified
- `dives/_conventions.tsx` — shared authoring reference (not deployed as a Dive)
- `dives/README.md` — deliverable model + SQL pre-flight + REQUIRED_DATABASES decision

## Decisions Made
- Derived `STRATEGIES` from `core/accounts.py` (12 strategies) as the authoritative live set; the research note's "13 strategies" includes unregistered ones that don't log trades.
- `REQUIRED_DATABASES` omitted for MCP-created Dives (creator owns `trading`).

## Deviations from Plan
None — plan executed as written. (`core/accounts.py` showed as pre-modified from earlier work; it was read only, never modified by this plan.)

## Issues Encountered
None. Tables are empty (Phases 1/2 unshipped of live data), which is the expected Wave 0 condition — empty-state paths in Wave 2 Dives cover it.

## Next Phase Readiness
- Wave 2 (Plans 02–05) unblocked: conventions, allow-list, and the verified table schema are in place.
- Each Wave 2 Dive will inline the conventions, run its SQL body via MCP `query`, then create the live Dive via `save_dive`.

---
*Phase: 03-dives*
*Completed: 2026-06-03*
