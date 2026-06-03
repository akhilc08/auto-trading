---
phase: 3
slug: dives
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-03
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **Dives cannot be unit-tested** (React components running in the MotherDuck browser UI against a live DB). Validation is SQL pre-flight checks (automatable via the MotherDuck MCP `query` tool) plus manual visual inspection. See `03-RESEARCH.md` → "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — Dives have no headless test harness. SQL verification via MotherDuck MCP `query` tool. |
| **Config file** | none |
| **Quick run command** | SQL pre-flight: `SELECT COUNT(*) FROM "trading"."main"."trades";` (via MCP `query`) |
| **Full suite command** | Run all four Dive SQL bodies via MCP `query` + open each Dive in the MotherDuck UI |
| **Estimated runtime** | ~30 seconds (SQL) + manual visual pass |

---

## Sampling Rate

- **After every task commit:** Run the Dive's SQL body via the MCP `query` tool and confirm it returns without error against the live `trading` DB
- **After every plan wave:** Run the SQL pre-flight block (all tables) from `03-RESEARCH.md`
- **Before `/gsd-verify-work`:** All four Dive SQL bodies execute cleanly AND each Dive opens in the UI without runtime error
- **Max feedback latency:** ~30 seconds (SQL execution)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1 | 03-01 | 1 | DIVES-01..04 (shared conventions + allow-list) | T-3-01 (SQL injection via strategy filter) | STRATEGIES closed allow-list mirrored from core/accounts.py; no raw interpolation | source/sql | `grep -q 'STRATEGIES' dives/_conventions.tsx && grep -q '#2d7a00' dives/_conventions.tsx` | dives/_conventions.tsx, dives/README.md | ⬜ pending |
| 03-01-T2 | 03-01 | 1 | DIVES-01..04 (Wave 0 gate) | — | Tables resolve + MCP reachable before authoring | sql (human-check) | SQL pre-flight block via MCP `query` (`SELECT COUNT(*)` UNION over the three tables) | n/a (gate) | ⬜ pending |
| 03-02-T1 | 03-02 | 2 | DIVES-01 | T-3-01 (SQL injection via strategy filter) | Strategy filter value constrained to the closed allow-list, validated before interpolation | sql | `SELECT COUNT(*) FROM "trading"."main"."trades" WHERE submitted_at >= current_date - 90` | dives/trade-log.tsx | ⬜ pending |
| 03-03-T1 | 03-03 | 2 | DIVES-02 | — | Static SQL, no user input; numeric cells N()-guarded | sql | `SELECT * FROM "trading"."main"."positions" QUALIFY row_number() OVER (PARTITION BY strategy_name, symbol ORDER BY snapshot_at DESC) = 1` | dives/live-positions.tsx | ⬜ pending |
| 03-04-T1 | 03-04 | 2 | DIVES-03 | — | Static SQL; COALESCE gap-fill prevents broken lines | sql | Run the generate_series gap-fill query; assert ~90 date rows per strategy, no NULL cumulative_pnl | dives/equity-curve.tsx | ⬜ pending |
| 03-05-T1 | 03-05 | 2 | DIVES-04 | — | Static SQL; NULLIF divide-by-zero guard on win rate | sql | Run the DIVES-04 metrics query; assert one row per strategy, no divide-by-zero | dives/strategy-comparison.tsx | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs assigned by the planner: `{plan}-T{n}` maps to the `<task>` order within each PLAN.md.*

---

## Wave 0 Requirements

- [ ] SQL pre-flight block from `03-RESEARCH.md` runs against the live `trading` DB (tables exist via Phase 1 `CREATE TABLE IF NOT EXISTS`) — gated by task 03-01-T2
- [ ] Confirm MotherDuck MCP tools (`create_dive` / `save_dive` / `query`) are reachable in this session — gated by task 03-01-T2

*No test framework to install — Dives are runtime-provided by MotherDuck.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Trade log table renders; strategy dropdown changes visible row set | DIVES-01 | Visual + interactive; no headless harness | Open Dive, confirm 90-day table; change strategy dropdown, confirm rows filter |
| Unrealized P&L cells colored green `#2d7a00` / red `#bc1200` | DIVES-02 | Color rendering is visual-only | Open Dive, confirm positive rows green, negative rows red |
| Equity-curve line chart has no time-series gaps; zero-trade strategy shows flat line at 0 | DIVES-03 | Chart rendering is visual-only | Open Dive, confirm continuous lines; no holes |
| All strategies appear with Sharpe/drawdown/win-rate/count/P&L | DIVES-04 | Table rendering is visual; cross-check vs SQL | Open Dive, confirm every strategy row present and matches SQL output |
| Each Dive renders a readable "No data yet" empty state | DIVES-01..04 | Empty-state path (Phases 1/2 may be unshipped) | With empty tables, confirm no crash/SQL error — readable empty message |

*Dives are inherently visual; automated SQL checks cover query correctness, manual checks cover rendering and interactivity.*

---

## Validation Sign-Off

- [x] Every Dive task has an `<automated>`/`<human-check>` SQL verify (query body executes cleanly) OR a documented manual verification
- [x] Sampling continuity: no 3 consecutive tasks without a SQL verify (every Dive task has a SQL verify)
- [ ] Wave 0 confirms tables + MCP reachability before authoring Dives (task 03-01-T2 — runs at execution)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter (planner reconciled task IDs)

**Approval:** planner-reconciled (task IDs assigned; Wave 0 gate runs at execution time)
