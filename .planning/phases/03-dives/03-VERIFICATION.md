---
phase: 03-dives
verified: 2026-06-03T22:05:00Z
status: human_needed
score: 4/4 must-have truths code-verified (final "shows data" confirmation requires human + non-empty tables)
overrides_applied: 0
human_verification:
  - test: "Open the trade-log Dive; confirm the 90-day table renders and changing the strategy dropdown filters the visible row set"
    expected: "Table shows trades from the last 90 days; selecting a strategy narrows rows to that strategy; 'All strategies' shows all"
    why_human: "Visual + interactive (dropdown re-query) with no headless harness; also requires non-empty trades table (currently 0 rows)"
  - test: "Open the live-positions Dive; confirm positive unrealized P&L renders green (#2d7a00) and negative renders red (#bc1200)"
    expected: "Latest snapshot per strategy; positive P&L cells green, negative red"
    why_human: "Color rendering is visual-only; requires non-empty positions table (currently 0 rows)"
  - test: "Open the equity-curve Dive; confirm each strategy is a continuous line with no time-axis gaps across weekends/holidays"
    expected: "One line per strategy; cumulative value carries forward flat across no-trade days (no sawtooth/drop to 0)"
    why_human: "Chart rendering is visual-only; requires non-empty daily_pnl table (currently 0 rows). SQL carry-forward logic is code-verified (CR-01 fixed) but the rendered no-gap result needs eyes on real data"
  - test: "Open the strategy-comparison Dive; confirm every strategy appears with Sharpe 7d, max drawdown, win rate %, trade count, total P&L matching the SQL"
    expected: "One row per strategy; metrics match a direct daily_pnl query; NULLs render as '—'"
    why_human: "Table rendering is visual; cross-check vs SQL requires non-empty daily_pnl (currently 0 rows)"
  - test: "With tables empty, confirm each of the four Dives renders the 'No data yet — run a strategy to populate.' empty state without crash or SQL error"
    expected: "Readable empty-state message, no runtime/SQL error"
    why_human: "Empty-state UI path; orchestrator confirmed SQL runs clean + Dives created, but the rendered empty state needs visual confirmation in the MotherDuck UI"
---

# Phase 3: Four MotherDuck Dives Verification Report

**Phase Goal:** Four Dives in MotherDuck make all trade, position, and performance data visible and interactive.
**Verified:** 2026-06-03T22:05:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (from PLAN must_haves + ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | Trade log Dive shows 90-day history filterable by strategy | ✓ VERIFIED (code) | `trade-log.tsx:44-58` SELECT over `"trading"."main"."trades"` with `submitted_at >= current_date - INTERVAL 90 DAY`, all DIVES-01 columns; `useDiveState` dropdown (l.29) built from STRATEGIES; filter appends `AND strategy_name = '<s>'` only when allow-listed |
| 2 | Live positions Dive shows open positions with green/red unrealized P&L | ✓ VERIFIED (code) | `live-positions.tsx:13-32` latest-snapshot-per-strategy via MAX(snapshot_at) CTE join; l.80-86 inline `style={{ color: N(r.unrealized_pnl) >= 0 ? PNL_GREEN : PNL_RED }}` with exact hex |
| 3 | Equity curve Dive shows per-strategy cumulative P&L with no time-series gaps | ✓ VERIFIED (code) | `equity-curve.tsx:34-70` date_spine generate_series CROSS JOIN strategies LEFT JOIN daily_pnl, `COALESCE(dp.realized_pnl, 0)` on the per-day delta then `SUM(realized_pnl) OVER (PARTITION BY strategy_name ORDER BY trade_date)` — CR-01 carry-forward fix confirmed (NOT COALESCE on cumulative value); useMemo long→wide pivot, one `<Line>` per strategy |
| 4 | Strategy comparison Dive shows Sharpe, drawdown, win rate, trade count, total P&L for all strategies | ✓ VERIFIED (code) | `strategy-comparison.tsx:15-26` GROUP BY strategy_name; AVG(sharpe_7d), MIN(max_drawdown) read (not recomputed); `100.0 * SUM(win_count) / NULLIF(SUM(trade_count), 0)`; SUM(trade_count); SUM(realized_pnl); fmt() renders NULL as "—" |

**Score:** 4/4 truths code-verified. The "shows data" / visual / interactive halves of each criterion require human confirmation against non-empty tables (see Human Verification).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `dives/_conventions.tsx` | N(), color constants, STRATEGIES allow-list, empty-state, table-name rules | ✓ VERIFIED | 106 lines; N(), PNL_GREEN/RED, 14-entry LINE_COLORS, 12-entry STRATEGIES, Array.isArray guard + "No data yet" documented |
| `dives/README.md` | Deliverable model + SQL pre-flight + REQUIRED_DATABASES decision | ✓ VERIFIED | File→Dive map, pre-flight block, Wave 0 result recorded |
| `dives/trade-log.tsx` | DIVES-01, useDiveState filter, 90-day, color-coded pnl | ✓ VERIFIED | 137 lines (>40); useDiveState + allow-list + regex guard |
| `dives/live-positions.tsx` | DIVES-02, latest snapshot, color-coded unrealized P&L | ✓ VERIFIED | 96 lines (>35); unrealized_pnl color-coded |
| `dives/equity-curve.tsx` | DIVES-03, generate_series gap-fill + recharts multi-line | ✓ VERIFIED | 135 lines (>60); LineChart, useMemo pivot, CR-01 fix |
| `dives/strategy-comparison.tsx` | DIVES-04, per-strategy metrics table | ✓ VERIFIED | 87 lines (>35); win_rate_pct, NULLIF guard |

All files committed (clean git status); commit hashes match SUMMARYs (823a483, 00d5809→f6a149b, c62f951, ea6bfba→f6a149b, 9d4f9fa).

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `_conventions.tsx` / `trade-log.tsx` | `core/accounts.py` | STRATEGIES mirrors registered names | ✓ WIRED | 12-entry list exactly matches `_ACCOUNT_STRATEGIES` (stat_arb x3, market_neutral x2, trend_following x2, regime_switching, vol_risk_premium, multi_factor_equity x2, post_earnings_drift) |
| `trade-log.tsx` | `trading.main.trades` | useSQLQuery SELECT | ✓ WIRED | Fully-qualified double-quoted table ref present |
| `trade-log.tsx` | STRATEGIES allow-list | filter dropdown + includes()+regex before interpolation | ✓ WIRED | T-3-01 mitigation: `.includes()` + `/^[a-z0-9_]+$/` (WR-04 fix), non-allow-list → no filter |
| `live-positions.tsx` | `trading.main.positions` | MAX(snapshot_at) CTE join | ✓ WIRED | Confirmed; #2d7a00 color present |
| `equity-curve.tsx` | `trading.main.daily_pnl` | generate_series spine CROSS JOIN LEFT JOIN | ✓ WIRED | useMemo pivot present |
| `strategy-comparison.tsx` | `trading.main.daily_pnl` | GROUP BY metrics SELECT + NULLIF | ✓ WIRED | NULLIF guard present |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| trade-log.tsx | `data` (rows) | useSQLQuery over trades | Tables empty (0 rows) — expected Wave 0 | ⚠️ EMPTY-by-design (orchestrator-confirmed; SQL runs clean) |
| live-positions.tsx | `data` (rows) | useSQLQuery over positions | 0 rows | ⚠️ EMPTY-by-design |
| equity-curve.tsx | `chartData` | useMemo over useSQLQuery daily_pnl | 0 rows | ⚠️ EMPTY-by-design |
| strategy-comparison.tsx | `data` (rows) | useSQLQuery over daily_pnl | 0 rows | ⚠️ EMPTY-by-design |

Schema cross-check: every queried column verified to exist in `core/motherduck_logger.py` (trades/positions/daily_pnl) and `flights/aggregation/daily_pnl.py` — no schema mismatch. Empty tables are the expected Wave 0 condition (Phases 1/2 have not logged live trades); the orchestrator executed each SQL body cleanly via MCP `query` and created/updated the live Dives via `save_dive`/`update_dive`. These are NOT gaps.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Dives are React/TSX in browser runtime, no headless harness | n/a | Per VALIDATION.md "Dives cannot be unit-tested" | ? SKIP (routed to human) |

Step 7b: SKIPPED for the runnable-app sense (Dives run in the MotherDuck UI, not locally). SQL-body execution was performed by the orchestrator via MCP (orchestrator-provided evidence).

### Probe Execution

No probes declared in PLAN/SUMMARY for this phase (Dive phase; validation is MCP SQL + manual visual per 03-VALIDATION.md). No `scripts/*/tests/probe-*.sh` applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DIVES-01 | 03-01, 03-02 | Trade log Dive, 90-day default, filterable by strategy via useDiveState | ✓ SATISFIED | trade-log.tsx |
| DIVES-02 | 03-01, 03-03 | Live positions, color-coded unrealized P&L, latest snapshot per strategy | ✓ SATISFIED | live-positions.tsx |
| DIVES-03 | 03-01, 03-04 | Equity curve line chart, generate_series gap fill, 90-day | ✓ SATISFIED | equity-curve.tsx (CR-01 fixed) |
| DIVES-04 | 03-01, 03-05 | Strategy comparison: Sharpe/drawdown/win-rate/count/P&L for all strategies | ✓ SATISFIED | strategy-comparison.tsx |

No orphaned requirements: REQUIREMENTS.md maps DIVES-01..04 to Phase 3, and every ID is claimed by a plan and implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (none) | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER in any Dive source | — | Clean |
| _conventions.tsx | 25 | "text-[#...]" appears only inside a comment forbidding Tailwind bracket syntax | ℹ️ Info | Not actual usage — documentation of the rule |

Advisory review findings NOT applied (documented as open in 03-REVIEW, non-blocking):
- WR-01 (equity-curve pivot duplicate-key collision) — theoretical; closed allow-list makes a strategy named `trade_date` impossible. ℹ️ Info.
- WR-03 (N() returns 0 for NULL nullable columns; trade-log/live-positions show 0.00 instead of "—") — data-fidelity advisory; strategy-comparison already uses fmt(). ⚠️ Cosmetic, non-blocking.
- IN-02 (`key={i}` array index) — harmless for wholesale-replaced query results. ℹ️ Info.

None of these block the phase goal. CR-01 (critical) and WR-04 (hardening) were fixed and committed (f6a149b).

### Human Verification Required

The phase goal includes "visible and interactive," and each ROADMAP success criterion has a visual/interactive half ("shows", "color-coded", "no gaps", "shows ... for all strategies") that cannot be confirmed programmatically AND requires non-empty tables (currently 0 rows by design). The code paths are all verified; the rendered behavior on real data needs human eyes. See the 5 items in `human_verification` frontmatter (trade-log filter, position colors, equity-curve gap-free lines, strategy-comparison metrics, empty-state rendering).

### Gaps Summary

No code gaps. All four Dive source files exist, are substantive, are wired to the correct fully-qualified tables, and use the shared conventions (N(), exact hex via inline style, Array.isArray guard, "No data yet" empty state). The T-3-01 injection guard is correctly implemented with the WR-04 defense-in-depth regex. The CR-01 sawtooth defect is genuinely fixed in `equity-curve.tsx` (running SUM over a spine-joined `daily` CTE with COALESCE on the per-day delta, not on the cumulative value). Every queried column matches the live schema. The orchestrator executed all SQL bodies via MCP and created/updated the four live Dives.

Status is `human_needed` (not `passed`) solely because the "visible and interactive" outcome — colors actually rendering, the dropdown actually filtering rows, the chart having no visible gaps, and tables showing real data — requires both human inspection in the MotherDuck UI and non-empty tables. Those are legitimately deferred-to-human checks per 03-VALIDATION.md's Manual-Only Verifications, not failures.

---

_Verified: 2026-06-03T22:05:00Z_
_Verifier: Claude (gsd-verifier)_
