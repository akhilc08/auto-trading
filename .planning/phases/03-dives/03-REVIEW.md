---
phase: 03-dives
reviewed: 2026-06-03T18:16:12Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - dives/_conventions.tsx
  - dives/trade-log.tsx
  - dives/live-positions.tsx
  - dives/equity-curve.tsx
  - dives/strategy-comparison.tsx
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-03T18:16:12Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the four deployed MotherDuck Dive components plus the shared authoring
reference. The components are well-structured: every numeric value is wrapped
with `N()`, all colors use inline style (no Tailwind bracket syntax), table refs
are fully qualified and double-quoted, and the empty/loading/error states are
present in all four Dives. The T-3-01 SQL-injection mitigation in `trade-log.tsx`
is correctly applied (see WR-04 for a residual hardening note).

The dominant issue is a **correctness defect in the equity-curve gap-fill** (CR-01):
the cumulative P&L series fills no-trade days with `0` instead of carrying forward
the last cumulative value, producing a sawtooth chart that directly violates the
phase's stated success criterion. The remaining findings are robustness gaps
(duplicate-key collisions, lexicographic date sort, NULL/Infinity handling).

I verified every queried column against the live schemas in
`core/motherduck_logger.py` (trades, positions, daily_pnl) and
`flights/aggregation/daily_pnl.py` — all column names and types match. No
schema-mismatch bugs found.

## Critical Issues

### CR-01: Equity-curve gap-fill resets cumulative P&L to 0 on no-trade days (sawtooth)

**File:** `dives/equity-curve.tsx:29-65`
**Issue:**
The `strategy_daily` CTE produces a row only for dates on which a strategy has a
`daily_pnl` row. The final query does `spine_cross LEFT JOIN strategy_daily ... COALESCE(sd.cumulative_pnl, 0)`.
For a **cumulative** series this is wrong: every date that has no `daily_pnl`
row (weekends, holidays, days the strategy did not trade) is filled with `0`
rather than the strategy's last cumulative value. The rendered line therefore
drops to `$0` on every gap day and jumps back up the next trading day — a
sawtooth, not a monotone-ish equity curve.

This contradicts the phase's own success criterion (`03-04-PLAN.md:14`):
"days with no trades show a continuous line (COALESCE to **last/zero**)" and the
threat-model row T-3-05 ("Missing COALESCE produces broken (gapped) line").
COALESCE-to-zero removes the SQL `NULL` but reintroduces the exact visual
brokenness the requirement was meant to prevent. Because `daily_pnl` is written
per trading day only (`flights/aggregation/daily_pnl.py` writes one row per
strategy per `PRIOR_DAY`), this defect triggers on the very first weekend in any
90-day window — i.e. always.

**Fix:**
Carry the last cumulative value forward across gap days. Compute the cumulative
sum over the full date spine after the join (so the window function sees the
gap-filled per-day deltas), e.g.:

```sql
WITH date_spine AS (
  SELECT unnest(generate_series(
    current_date - INTERVAL 89 DAY, current_date, INTERVAL 1 DAY))::DATE AS trade_date
),
strategies AS (
  SELECT DISTINCT strategy_name FROM "trading"."main"."daily_pnl"
),
spine_cross AS (
  SELECT d.trade_date, s.strategy_name
  FROM date_spine d CROSS JOIN strategies s
),
daily AS (   -- per-day realized_pnl, 0 on gap days (deltas may legitimately be 0)
  SELECT sc.trade_date, sc.strategy_name,
         COALESCE(dp.realized_pnl, 0) AS realized_pnl
  FROM spine_cross sc
  LEFT JOIN "trading"."main"."daily_pnl" dp
    ON dp.date = sc.trade_date AND dp.strategy_name = sc.strategy_name
)
SELECT
  strftime(trade_date, '%Y-%m-%d') AS trade_date,
  strategy_name,
  SUM(realized_pnl) OVER (
    PARTITION BY strategy_name ORDER BY trade_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_pnl
FROM daily
ORDER BY trade_date, strategy_name
```

COALESCE on the *per-day delta* to 0 is correct (no trades = no P&L change); the
running `SUM(...)` then keeps the cumulative value flat across gaps instead of
collapsing it to 0.

## Warnings

### WR-01: Equity-curve pivot drops rows on duplicate (date, strategy) keys

**File:** `dives/equity-curve.tsx:71-87`
**Issue:**
The pivot does `byDate[date][strat] = N(r.cumulative_pnl)`. If the query ever
returns more than one row for the same `(trade_date, strategy_name)`, the later
row silently overwrites the earlier one with no error. The current SQL should
yield unique pairs, but this is a load-bearing assumption with no guard — and the
`strategy_name` value is used directly as an object key, so a strategy literally
named `trade_date` would collide with the date key written at line 77
(`byDate[date] = { trade_date: date }`) and corrupt the chart. With the closed
strategy allow-list this is unlikely, but the pivot makes no defensive check.

**Fix:**
Namespace strategy keys to avoid collision with the reserved `trade_date` field,
e.g. store series under a prefixed key (`s_<strategy>`) and map it back when
rendering `<Line dataKey=...>`, or assert uniqueness. At minimum, guard against a
strategy named `trade_date`.

### WR-02: Equity-curve sorts dates lexicographically as strings

**File:** `dives/equity-curve.tsx:82-84`
**Issue:**
`Object.values(byDate).sort((a, b) => String(a.trade_date) > String(b.trade_date) ? 1 : -1)`
sorts on the `%Y-%m-%d` string. This happens to work for zero-padded ISO dates,
but (a) it relies entirely on the SQL `strftime` format never changing, and (b)
the comparator returns `1`/`-1` and never `0` for equal values, which is an
unstable/technically-incorrect comparator (equal elements get reordered). The SQL
already emits `ORDER BY sc.trade_date`, so re-sorting in JS is also redundant work
that can only introduce divergence from the query order.

**Fix:**
Drop the JS sort and rely on the SQL `ORDER BY` (the pivot preserves insertion
order of `Object.values` for string keys in insertion order in practice, but
safest is to sort the date keys explicitly): build the array by iterating sorted
`Object.keys(byDate)`, or return a proper comparator
`(a, b) => String(a.trade_date).localeCompare(String(b.trade_date))`.

### WR-03: `N()` returns 0 for non-numeric/NaN values, silently masking bad data

**File:** `dives/trade-log.tsx:4`, `dives/live-positions.tsx:4`, `dives/equity-curve.tsx:15`, `dives/strategy-comparison.tsx:4`
**Issue:**
`N = (v) => (v != null ? Number(v) : 0)` returns `NaN` when `v` is a non-numeric
string or an object that does not coerce (e.g. an unexpected struct), and
`NaN.toFixed(2)` renders the literal string `"NaN"` in the table. Conversely, a
genuine `NULL` from SQL becomes `0`, which is indistinguishable from a real zero —
e.g. a `NULL` `filled_avg_price` (the column is nullable for unfilled orders)
renders as `0.00`, implying a $0 fill price rather than "not filled". This is a
data-fidelity issue in `trade-log` (filled_avg_price/pnl are nullable) and
`live-positions` (current_price/unrealized_pnl are nullable).

**Fix:**
For nullable numeric columns, render an explicit placeholder for NULL the way
`strategy-comparison.tsx` already does with its `fmt()` helper
(`v == null ? "—" : N(v).toFixed(digits)`). Reuse that `fmt()` pattern in
`trade-log.tsx` (filled_avg_price, pnl) and `live-positions.tsx`
(current_price, unrealized_pnl) so NULL is shown as "—" instead of a misleading
`0.00`.

### WR-04: SQL filter relies solely on the allow-list; single-quote is the only injection vector and it is closed, but no escaping defense-in-depth

**File:** `dives/trade-log.tsx:33-36`
**Issue:**
The T-3-01 mitigation is correctly implemented: `strategy !== "all" && STRATEGIES.includes(strategy)`
gates interpolation, and every value in `STRATEGIES` is a safe `[a-z_0-9]`
identifier, so the interpolated string cannot contain a quote or SQL
metacharacter. This is sound as written. The residual risk is purely
maintenance-time: the safety is an emergent property of the allow-list contents,
not of the interpolation site. If a future strategy name containing a `'` (or any
metacharacter) is added to `STRATEGIES` — or if someone copies this
`includes`-then-interpolate pattern to a column that is not allow-listed — the
guard silently stops protecting. There is no parameterization and no escaping as
a second layer.

**Fix:**
Keep the allow-list (it is the right primary control), but make the safety local
to the interpolation site rather than dependent on allow-list contents. Either
add an assertion that the value matches `/^[a-z0-9_]+$/` immediately before
interpolation, or use the runtime's parameter-binding mechanism if `useSQLQuery`
exposes one. At minimum, add a comment-anchored invariant test that every
`STRATEGIES` entry matches `^[a-z0-9_]+$`.

## Info

### IN-01: Duplicate `strategies` semantics between two CTEs is fragile

**File:** `dives/equity-curve.tsx:37-51`
**Issue:**
`strategy_daily` filters `daily_pnl` to the last 89 days, while `strategies`
(`SELECT DISTINCT strategy_name FROM daily_pnl`) scans all history. A strategy
that traded >90 days ago but not within the window will appear as a flat `$0`
line for the entire chart (an empty series). This is cosmetic given the
data-retention assumptions, but the two different time scopes for "which
strategies exist" vs "which strategies have window data" are an easy source of
confusion.

**Fix:**
Derive the strategy set from the same 90-day window
(`SELECT DISTINCT strategy_name FROM daily_pnl WHERE date >= current_date - INTERVAL 89 DAY`)
so only strategies active in the window get a line.

### IN-02: `key={i}` uses array index as React key in all four tables

**File:** `dives/trade-log.tsx:109`, `dives/live-positions.tsx:70`, `dives/strategy-comparison.tsx:68`
**Issue:**
Rows use the array index as the React `key`. For static, fully re-rendered query
results this is harmless, but it defeats React's reconciliation if the list ever
becomes incrementally updated/sorted client-side, and it is the documented
anti-pattern. Low risk here because rows are replaced wholesale on each query.

**Fix:**
Use a stable natural key where one exists (e.g. `${r.strategy_name}-${r.symbol}-${r.submitted_at}`
in trade-log, `${r.strategy_name}-${r.symbol}` in live-positions, `r.strategy_name`
in strategy-comparison). Keep `key={i}` only where no natural key exists.

---

_Reviewed: 2026-06-03T18:16:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
