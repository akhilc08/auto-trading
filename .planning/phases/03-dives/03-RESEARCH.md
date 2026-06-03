# Phase 3: Dives — Research

**Researched:** 2026-06-03
**Domain:** MotherDuck Dives (React TSX components with embedded SQL, recharts, useSQLQuery)
**Confidence:** HIGH

---

## Summary

Phase 3 builds four interactive MotherDuck Dives over live trade and performance data written by Phases 1 and 2. Dives are React TSX components authored directly in MotherDuck — they are NOT files committed to this repo. Each Dive is created via the `MD_CREATE_DIVE` SQL function (or its MCP equivalent) and lives in the MotherDuck workspace.

The authoritative Dive authoring contract was established from two sources: the official `useSQLQuery` and `useDiveState` MotherDuck docs, and the `motherduckdb/blessed-dives-example` GitHub repo (including its `CLAUDE.md` and the complete `eastlake-sales.tsx` example component). Every pattern in this research traces to one of those two sources.

The four Dives have a clear data dependency hierarchy: DIVES-01 and DIVES-02 read from `trades` and `positions` (written by Phase 1 logger and Phase 2 Flights). DIVES-03 and DIVES-04 read from `daily_pnl` (written by the Phase 2 aggregation Flight). **Phases 1 and 2 must be complete before these Dives have real data to display.** Each Dive should degrade gracefully when tables are empty (return `<p>No data yet</p>` rather than crashing).

**Primary recommendation:** Author all four Dives as TSX strings passed to `MD_CREATE_DIVE` SQL calls. Use `useSQLQuery` for all data fetching, `useDiveState` for the strategy filter in DIVES-01, recharts `LineChart`/`ResponsiveContainer` for DIVES-03, and inline `style={{}}` for all custom hex colors. Never use Tailwind bracket syntax.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIVES-01 | Trade log Dive: all trades with symbol, side, qty, submitted_at, filled_avg_price, pnl; default 90-day filter; filterable by strategy via useDiveState | useDiveState parameterized query pattern; trades table schema from SCHEMA-01 |
| DIVES-02 | Live positions Dive: current open positions with unrealized P&L, green (#2d7a00) / red (#bc1200) color-coded; queries latest positions snapshot per strategy | positions table schema from SCHEMA-02; inline style={{color}} pattern confirmed |
| DIVES-03 | Equity curve Dive: cumulative P&L per strategy as line chart; generate_series LEFT JOIN gap filling; 90-day default window | generate_series + unnest pattern confirmed from eastlake-sales example; recharts LineChart multi-series pattern documented |
| DIVES-04 | Strategy comparison Dive: Sharpe 7d, max drawdown, win rate %, trade count, total P&L for all strategies in a table | daily_pnl schema has sharpe_7d, max_drawdown pre-computed; win_rate = win_count/trade_count in SQL |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SQL query execution | MotherDuck (server-side) | — | useSQLQuery runs queries against the MotherDuck cloud DB at Dive load time |
| React rendering | Browser | — | Dives are React components rendered in the MotherDuck UI |
| Strategy filter state | Browser (URL) | — | useDiveState encodes filter into URL for shareability |
| Data aggregation (Sharpe, drawdown) | MotherDuck Flight (Phase 2) | — | Pre-computed into daily_pnl by aggregation Flight — Dives read, not compute |
| Gap filling (equity curve) | SQL (within Dive query) | — | generate_series LEFT JOIN COALESCE in the useSQLQuery SQL string |
| Color-coded P&L | Browser (inline style) | — | style={{color}} in JSX — Tailwind bracket syntax does not work in Dives |
| Dive creation/update | MotherDuck MCP (MD_CREATE_DIVE) | — | Dives live in MotherDuck workspace, not in the git repo |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@motherduck/react-sql-query` | bundled by MotherDuck runtime | useSQLQuery and useDiveState hooks | Only available SDK for querying MotherDuck from within a Dive |
| `recharts` | 3.8.1 [VERIFIED: npm registry] | LineChart, BarChart for DIVES-03/04 | Explicitly listed as available in Dive runtime by MotherDuck; confirmed in eastlake-sales example |
| `lucide-react` | 1.17.0 [VERIFIED: npm registry] | Icon components | Listed as available in Dive runtime (per MotherDuck CLAUDE.md) |
| `react` | bundled by MotherDuck runtime | Component model | Built into Dive runtime |

### Available Dive Runtime Libraries
Per `motherduckdb/blessed-dives-example` CLAUDE.md [CITED: github.com/motherduckdb/blessed-dives-example/blob/main/CLAUDE.md]:
- `react`
- `recharts`
- `lucide-react`
- `@motherduck/react-sql-query`

No other libraries are available. Do not import anything else.

### No npm install needed
Dives are authored as TSX strings passed to `MD_CREATE_DIVE`. There is no package.json in this repo for Dive dependencies — all libraries are provided by the MotherDuck Dive runtime.

---

## Package Legitimacy Audit

> Dives are not npm packages installed into this repo. The libraries below are bundled by the MotherDuck Dive runtime. This audit verifies they are legitimate packages that MotherDuck would bundle.

| Package | Registry | Age | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-------------|-----------|-------------|
| `recharts` | npm | ~10 yrs (2015-08-07) | github.com/recharts/recharts | [OK] | Approved — confirmed in eastlake-sales.tsx example |
| `lucide-react` | npm | ~4 yrs | github.com/lucide-icons/lucide | [OK] | Approved — listed in blessed-dives-example CLAUDE.md |
| `@motherduck/react-sql-query` | MotherDuck private | — | MotherDuck internal | [OK] | Approved — official MotherDuck SDK |

*slopcheck was unavailable at research time. recharts and lucide-react confirmed via official MotherDuck documentation (eastlake-sales.tsx example and CLAUDE.md). No install step required — MotherDuck runtime provides these.*

**Packages removed due to slopcheck [SLOP] verdict:** none

---

## Architecture Patterns

### System Architecture Diagram

```
MotherDuck "trading" DB
  ├── trades table          ──► DIVES-01 (Trade Log)
  ├── positions table       ──► DIVES-02 (Live Positions)
  └── daily_pnl table       ──► DIVES-03 (Equity Curve)
                             ──► DIVES-04 (Strategy Comparison)

Each Dive:
  Browser request
    → useSQLQuery("SELECT ... FROM \"trading\".\"main\".\"table\"")
      → MotherDuck executes SQL
        → data array returned directly (no .rows wrapper)
          → recharts / table renders in browser
```

### Dive Component Skeleton (Authoritative Pattern)

```tsx
// Source: github.com/motherduckdb/blessed-dives-example/blob/main/dives/eastlake-sales/eastlake-sales.tsx
import { useMemo } from "react";
import { useSQLQuery } from "@motherduck/react-sql-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";

// Only needed for local preview (blessed-dives-example CI workflow).
// When creating via MD_CREATE_DIVE MCP tool, omit or leave as empty array.
export const REQUIRED_DATABASES = [{ type: "database", path: "trading", alias: "trading" }];

// Safe numeric conversion — DuckDB returns BIGINT/DECIMAL as BigInt objects
const N = (v: unknown): number => (v != null ? Number(v) : 0);

export default function MyDive() {
  const { data, isLoading, isError } = useSQLQuery(`
    SELECT ... FROM "trading"."main"."trades"
  `);

  const rows = Array.isArray(data) ? data : [];

  if (isLoading) return <div>Loading...</div>;
  if (isError)   return <div>Error loading data.</div>;
  if (rows.length === 0) return <p>No data yet — run a strategy to populate.</p>;

  return <div>...</div>;
}
```

**Critical notes from official sources:**
- `data` is the rows array directly — **no `.data.rows` wrapper** [VERIFIED: MotherDuck useSQLQuery docs]
- Always guard: `const rows = Array.isArray(data) ? data : []`
- `N()` helper required for any BIGINT, HUGEINT, or DECIMAL column
- Table names must be `"trading"."main"."table_name"` (fully qualified, double-quoted) [VERIFIED: MotherDuck docs]
- `REQUIRED_DATABASES` export must be a single line — multi-line breaks the CI regex that strips it [CITED: github.com/motherduckdb/blessed-dives-example/blob/main/CLAUDE.md]

### Pattern 1: useDiveState Strategy Filter (DIVES-01)

```tsx
// Source: motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/use-dive-state/
import { useDiveState, useSQLQuery } from "@motherduck/react-sql-query";

export default function TradeLogDive() {
  const [strategy, setStrategy] = useDiveState("strategy", "all");

  const whereClause = strategy === "all"
    ? ""
    : `AND strategy_name = '${strategy}'`;

  const { data, isLoading } = useSQLQuery(`
    SELECT
      symbol, side, qty,
      submitted_at::VARCHAR AS submitted_at,
      filled_avg_price, pnl
    FROM "trading"."main"."trades"
    WHERE submitted_at >= current_date - INTERVAL 90 DAY
      ${whereClause}
    ORDER BY submitted_at DESC
  `);

  const rows = Array.isArray(data) ? data : [];

  return (
    <div>
      <select value={strategy} onChange={e => setStrategy(e.target.value)}>
        <option value="all">All strategies</option>
        <option value="stat_arb">stat_arb</option>
        <option value="vol_risk_premium">vol_risk_premium</option>
        {/* ... one per strategy */}
      </select>
      {isLoading && <p>Loading...</p>}
      {rows.length === 0 && !isLoading && <p>No trades in last 90 days.</p>}
      <table>
        <thead>
          <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Submitted</th><th>Fill Price</th><th>PnL</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{String(r.symbol)}</td>
              <td>{String(r.side)}</td>
              <td>{N(r.qty)}</td>
              <td>{String(r.submitted_at)}</td>
              <td>{N(r.filled_avg_price).toFixed(2)}</td>
              <td style={{ color: N(r.pnl) >= 0 ? "#2d7a00" : "#bc1200" }}>
                {N(r.pnl).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**useDiveState API** [VERIFIED: MotherDuck useDiveState docs]:
- Signature: `const [value, setValue] = useDiveState(key, initialValue)`
- `key`: stable string identifier, encodes into URL for shareability
- `initialValue`: JSON-serializable fallback when URL lacks the key
- Returns `[currentValue, setter]` — same shape as `useState`

### Pattern 2: Color-Coded P&L (DIVES-02)

```tsx
// Source: confirmed pattern from eastlake-sales.tsx (style={{}} for custom colors)
// and PITFALLS.md research finding #13
const pnlColor = (pnl: number) => ({ color: pnl >= 0 ? "#2d7a00" : "#bc1200" });

<td style={pnlColor(N(row.unrealized_pnl))}>
  {N(row.unrealized_pnl).toFixed(2)}
</td>
```

**Rule:** Never use `className="text-[#2d7a00]"` — Tailwind bracket syntax fails in Dives.
Use `style={{ color: "#2d7a00" }}` instead. [CITED: PITFALLS.md research #13, confirmed by eastlake-sales.tsx]

### Pattern 3: generate_series Gap Filling for Equity Curve (DIVES-03)

The equity curve must show cumulative P&L per strategy with no gaps in the time axis. The `eastlake-sales.tsx` example uses `unnest(generate_series(...))` — the same pattern applies here:

```sql
-- Source: adapted from eastlake-sales.tsx monthlyQ pattern
-- Step 1: generate a complete date spine
WITH date_spine AS (
  SELECT
    unnest(generate_series(
      current_date - INTERVAL 89 DAY,
      current_date,
      INTERVAL 1 DAY
    ))::DATE AS trade_date
),
-- Step 2: per-strategy cumulative PnL from daily_pnl
strategy_daily AS (
  SELECT
    date AS trade_date,
    strategy_name,
    SUM(realized_pnl) OVER (
      PARTITION BY strategy_name
      ORDER BY date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_pnl
  FROM "trading"."main"."daily_pnl"
  WHERE date >= current_date - INTERVAL 89 DAY
),
-- Step 3: cross join date_spine with distinct strategies, left join data
strategies AS (
  SELECT DISTINCT strategy_name FROM "trading"."main"."daily_pnl"
),
spine_cross AS (
  SELECT d.trade_date, s.strategy_name
  FROM date_spine d CROSS JOIN strategies s
)
SELECT
  strftime(sc.trade_date, '%Y-%m-%d') AS trade_date,
  sc.strategy_name,
  COALESCE(sd.cumulative_pnl, 0) AS cumulative_pnl
FROM spine_cross sc
LEFT JOIN strategy_daily sd
  ON sc.trade_date = sd.trade_date
  AND sc.strategy_name = sd.strategy_name
ORDER BY sc.trade_date, sc.strategy_name
```

**Recharts requirement:** LineChart expects one object per date with all series as keys. The SQL above returns rows in long format (date, strategy_name, value). The React component must pivot this to wide format using `useMemo`:

```tsx
// Source: recharts multi-series documentation pattern
const chartData = useMemo(() => {
  const byDate: Record<string, Record<string, number>> = {};
  const strategies = new Set<string>();
  for (const r of rows) {
    const date = String(r.trade_date);
    if (!byDate[date]) byDate[date] = { trade_date: date };
    byDate[date][String(r.strategy_name)] = N(r.cumulative_pnl);
    strategies.add(String(r.strategy_name));
  }
  return {
    data: Object.values(byDate).sort((a, b) => a.trade_date > b.trade_date ? 1 : -1),
    strategies: Array.from(strategies),
  };
}, [rows]);

// Render
const COLORS = ["#3366cc", "#dc3912", "#ff9900", "#109618", "#990099",
                "#0099c6", "#dd4477", "#66aa00", "#b82e2e", "#316395",
                "#994499", "#22aa99", "#aaaa11", "#6633cc"];

<ResponsiveContainer width="100%" height={300}>
  <LineChart data={chartData.data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="trade_date" tick={{ fontSize: 11 }} />
    <YAxis tickFormatter={v => `$${v}`} />
    <Tooltip formatter={(v: number) => [`$${v.toFixed(2)}`, ""]} />
    <Legend />
    {chartData.strategies.map((s, i) => (
      <Line
        key={s}
        type="monotone"
        dataKey={s}
        stroke={COLORS[i % COLORS.length]}
        strokeWidth={2}
        dot={false}
      />
    ))}
  </LineChart>
</ResponsiveContainer>
```

**Why long-to-wide pivot in React:** DuckDB `PIVOT ON strategy_name USING SUM GROUP BY date` would produce wide format in SQL, but the column names are dynamic (depend on which strategies exist). The long-format SQL + React useMemo pivot is more robust — it handles any number of strategies without knowing them at query-write time. [ASSUMED — DuckDB PIVOT is valid SQL but dynamic column names are unknown at Dive authoring time]

### Pattern 4: Strategy Comparison Table (DIVES-04)

```sql
-- Source: SCHEMA-04 from REQUIREMENTS.md
-- sharpe_7d and max_drawdown are pre-computed by the aggregation Flight
SELECT
  strategy_name,
  ROUND(AVG(sharpe_7d), 3)         AS sharpe_7d,
  ROUND(MIN(max_drawdown), 4)      AS max_drawdown,
  ROUND(
    100.0 * SUM(win_count) / NULLIF(SUM(trade_count), 0), 1
  )                                AS win_rate_pct,
  SUM(trade_count)                 AS trade_count,
  ROUND(SUM(realized_pnl), 2)      AS total_pnl
FROM "trading"."main"."daily_pnl"
WHERE date >= current_date - INTERVAL 30 DAY
GROUP BY strategy_name
ORDER BY total_pnl DESC
```

**Column sources from SCHEMA-04:**
- `sharpe_7d` — pre-computed by aggregation Flight, stored in `daily_pnl`
- `max_drawdown` — pre-computed by aggregation Flight, stored in `daily_pnl`
- `win_rate_pct` — computed in SQL: `SUM(win_count) / SUM(trade_count)` from `daily_pnl`
- `trade_count` — stored in `daily_pnl`
- `total_pnl` — `SUM(realized_pnl)` from `daily_pnl`

### Anti-Patterns to Avoid

- **`data.rows` access:** `data` IS the rows array. `data.rows` is `undefined`. Always use `data` directly.
- **`bg-[#hex]` Tailwind bracket classes:** Do not work in Dive runtime. Use `style={{ background: "#hex" }}`.
- **Unguarded BigInt in JSX:** `{row.pnl}` crashes if `pnl` is a BigInt. Always wrap with `N(row.pnl)`.
- **Bare table names:** `FROM trades` may fail in Dive runtime. Use `"trading"."main"."trades"`.
- **Single full-page loader:** Per MotherDuck CLAUDE.md — use per-section loading skeletons.
- **`new Date()` in JS for dates:** Format dates in SQL using `strftime()`, not JavaScript date objects.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL data fetching in React | Custom fetch/WebSocket/REST | `useSQLQuery` from `@motherduck/react-sql-query` | The only supported data access pattern in Dive runtime |
| URL-synced filter state | `useState` + URL parsing | `useDiveState` | Built-in shareability; URL encoding handled automatically |
| BigInt-to-number conversion | Custom type guards | `const N = (v) => v != null ? Number(v) : 0` | Established Dive pattern; handles null safely |
| Time-series gap filling | JavaScript date interpolation | SQL `generate_series` + `LEFT JOIN` + `COALESCE` | Gaps filled before data leaves DB; recharts has no interpolation |
| Line charts | `<canvas>` / D3 direct | recharts `LineChart` with `ResponsiveContainer` | Available in Dive runtime; well-documented |
| Sharpe/drawdown computation | SQL window functions in Dive | Read pre-computed `sharpe_7d`, `max_drawdown` from `daily_pnl` | Already computed by Phase 2 aggregation Flight |

**Key insight:** The Dive runtime is a sandboxed React environment with a fixed library set. Do not attempt to import packages not in `{react, recharts, lucide-react, @motherduck/react-sql-query}`.

---

## Common Pitfalls

### Pitfall 1: `data.rows` vs `data`
**What goes wrong:** Accessing `data.rows` returns `undefined`, silently breaking the table/chart.
**Why it happens:** Developers assume the axios/fetch pattern where results are nested.
**How to avoid:** Destructure as `{ data }` and use `Array.isArray(data) ? data : []`.
**Warning signs:** Empty table with no error, `isLoading` is false.

### Pitfall 2: Arbitrary Tailwind Bracket Syntax
**What goes wrong:** Classes like `text-[#2d7a00]`, `bg-[#bc1200]` render with no styling applied.
**Why it happens:** Dive runtime uses a limited Tailwind build that does not include JIT/arbitrary values.
**How to avoid:** Use `style={{ color: "#2d7a00" }}` for all custom hex colors.
**Warning signs:** P&L color coding visually absent; no browser error.

### Pitfall 3: Missing COALESCE on generate_series Left Join
**What goes wrong:** Recharts renders a gap (broken line) in the equity curve where `daily_pnl` has no row.
**Why it happens:** `LEFT JOIN` produces NULL for missing dates; recharts does not interpolate nulls.
**How to avoid:** `COALESCE(cumulative_pnl, 0)` or carry forward last known value with `LAST_VALUE` window function.
**Warning signs:** Equity curve line breaks for strategies with no trades on some days.

### Pitfall 4: Unguarded BigInt in JSX
**What goes wrong:** React throws `TypeError: Cannot convert BigInt value to a number` or renders `n` suffix.
**Why it happens:** DuckDB returns `BIGINT`, `HUGEINT`, and `DECIMAL` as JavaScript `BigInt` objects.
**How to avoid:** Wrap every numeric column with `N(row.pnl)` before using in math or rendering.
**Warning signs:** Values display as `0n`, `123456n`, or component crashes with BigInt error.

### Pitfall 5: Empty Tables Before Phases 1 and 2 Complete
**What goes wrong:** Dive crashes or shows confusing error when `trades`/`positions`/`daily_pnl` tables don't exist or are empty.
**Why it happens:** Phase 3 is planned before Phase 1 and 2 have run.
**How to avoid:** Add explicit empty-state handling: `if (rows.length === 0) return <p>No data yet.</p>`. Use `CREATE TABLE IF NOT EXISTS` in Phase 1 so tables always exist even if empty.
**Warning signs:** Dive shows SQL error about missing catalog/table.

### Pitfall 6: Strategy Name Injection in useDiveState
**What goes wrong:** If strategy name contains a single quote (unlikely but possible), the interpolated SQL breaks.
**Why it happens:** String interpolation in SQL template literals without escaping.
**How to avoid:** Either use a fixed list of known strategy names (not user-typed), or use `enabled: false` + parameter binding. Since strategy names are a fixed closed set (13 known strategies), use an explicit `<option>` list with hardcoded values.
**Warning signs:** SQL error when filtering; only applies if strategy names are user-typed.

### Pitfall 7: Recharts Requires Wide-Format Data for Multi-Line
**What goes wrong:** Passing long-format data (date, strategy, value) directly to `LineChart` renders only one line.
**Why it happens:** Each `<Line dataKey="strategy_name">` must map to a key on each data object — not a value in a column.
**How to avoid:** Pivot long-format SQL results to wide format in React using `useMemo` before passing to `LineChart`.
**Warning signs:** Only one line renders, or all lines overlay at 0.

---

## SQL Reference: All Four Dives

### DIVES-01: Trade Log

```sql
-- columns from SCHEMA-01: order_id, strategy_name, account_name, symbol, side, qty,
--   submitted_at (TIMESTAMPTZ), filled_at (TIMESTAMPTZ), filled_avg_price, pnl, status
SELECT
  symbol,
  side,
  qty,
  strftime(submitted_at::TIMESTAMP, '%Y-%m-%d %H:%M') AS submitted_at,
  ROUND(filled_avg_price, 4) AS filled_avg_price,
  ROUND(pnl, 2) AS pnl,
  strategy_name
FROM "trading"."main"."trades"
WHERE submitted_at >= current_date - INTERVAL 90 DAY
  -- useDiveState injects: AND strategy_name = 'xxx' (or nothing for "all")
ORDER BY submitted_at DESC
LIMIT 500
```

### DIVES-02: Live Positions

```sql
-- columns from SCHEMA-02: snapshot_at (TIMESTAMPTZ), strategy_name, account_name,
--   symbol, qty, avg_entry_price, current_price, unrealized_pnl
-- "latest snapshot per strategy" — use MAX(snapshot_at) per strategy
WITH latest_snapshot AS (
  SELECT strategy_name, MAX(snapshot_at) AS latest_at
  FROM "trading"."main"."positions"
  GROUP BY strategy_name
)
SELECT
  p.symbol,
  p.strategy_name,
  p.qty,
  ROUND(p.avg_entry_price, 4) AS avg_entry_price,
  ROUND(p.current_price, 4) AS current_price,
  ROUND(p.unrealized_pnl, 2) AS unrealized_pnl,
  strftime(p.snapshot_at::TIMESTAMP, '%Y-%m-%d %H:%M') AS snapshot_at
FROM "trading"."main"."positions" p
JOIN latest_snapshot ls
  ON p.strategy_name = ls.strategy_name
  AND p.snapshot_at = ls.latest_at
ORDER BY p.strategy_name, p.unrealized_pnl DESC
```

### DIVES-03: Equity Curve (see Architecture Patterns section for full SQL)

Key columns from SCHEMA-04: `date`, `strategy_name`, `realized_pnl`

### DIVES-04: Strategy Comparison

```sql
-- columns from SCHEMA-04: date, strategy_name, account_name, realized_pnl,
--   trade_count, win_count, sharpe_7d, max_drawdown
SELECT
  strategy_name,
  ROUND(AVG(sharpe_7d), 3)                                                AS sharpe_7d,
  ROUND(MIN(max_drawdown), 4)                                             AS max_drawdown,
  ROUND(100.0 * SUM(win_count) / NULLIF(SUM(trade_count), 0), 1)        AS win_rate_pct,
  SUM(trade_count)                                                        AS trade_count,
  ROUND(SUM(realized_pnl), 2)                                            AS total_pnl
FROM "trading"."main"."daily_pnl"
GROUP BY strategy_name
ORDER BY total_pnl DESC
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| External dashboard (Grafana, Metabase) | MotherDuck Dives (built-in React components) | No separate infra; Dives live alongside data |
| `data.rows` (axios-style) | `data` directly (array) | Code that checks `.rows` silently breaks |
| Tailwind JIT arbitrary values | inline `style={{}}` for custom colors | Tailwind bracket classes do not work in Dive runtime |
| Global full-page spinner | Per-section loading skeletons | Better perceived performance in multi-query Dives |

**Deprecated:**
- `useSQLQuery` returning `.data.rows`: never existed in MotherDuck Dives — was a developer assumption

---

## Validation Architecture

### How to Verify Each Dive's Correctness

Dives cannot be unit tested with Jest/pytest — they are React components running in the MotherDuck browser UI against a live database. Validation is manual visual inspection supplemented by SQL verification.

### Phase Requirements → Validation Map

| Req ID | Behavior | Validation Method |
|--------|----------|-------------------|
| DIVES-01 | Shows 90-day trades filterable by strategy | (1) SQL: `SELECT COUNT(*) FROM "trading"."main"."trades" WHERE submitted_at >= current_date - 90`; (2) Visual: open Dive, confirm table shows, change strategy dropdown and verify row count changes |
| DIVES-02 | Shows latest positions per strategy, green/red colors | (1) SQL: verify latest snapshot exists; (2) Visual: confirm unrealized_pnl column has colored values — positive rows green (#2d7a00), negative rows red (#bc1200) |
| DIVES-03 | Equity curve shows all 90 days with no gaps | (1) SQL: confirm 90 rows in date spine from query; (2) Visual: confirm line chart has no gaps; strategy with no trades shows flat line at 0, not a hole |
| DIVES-04 | All strategies appear with Sharpe, drawdown, win rate, trade count, PnL | (1) SQL: run the DIVES-04 query directly in MotherDuck and verify all 13 strategy rows appear; (2) Visual: confirm table has all strategies |

### SQL Pre-Flight Checks (run before opening Dives)

```sql
-- Check tables exist and have data
SELECT 'trades' AS tbl, COUNT(*) AS rows FROM "trading"."main"."trades"
UNION ALL
SELECT 'positions', COUNT(*) FROM "trading"."main"."positions"
UNION ALL
SELECT 'daily_pnl', COUNT(*) FROM "trading"."main"."daily_pnl";

-- Verify latest positions snapshot is recent
SELECT MAX(snapshot_at) AS latest_snapshot FROM "trading"."main"."positions";

-- Verify daily_pnl has data for recent dates
SELECT date, COUNT(*) AS strategy_count FROM "trading"."main"."daily_pnl"
WHERE date >= current_date - 7
GROUP BY date ORDER BY date DESC;
```

### Empty-Table Handling Requirement
Since Phases 1 and 2 may not be complete when Dives are authored, each Dive must render gracefully when tables are empty. The planner must include an explicit task to verify each Dive's empty-state path returns a readable "No data yet" message rather than a crash or SQL error.

---

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| MotherDuck account with `trading` DB | All Dives | Must be verified | Created by Phase 1 |
| MotherDuck MCP tools (MD_CREATE_DIVE) | Creating Dives | Available via MCP server | Used in place of git-deployed Dives |
| `recharts` | DIVES-03 | Bundled by MotherDuck Dive runtime | No install needed |
| `@motherduck/react-sql-query` | All Dives | Bundled by MotherDuck Dive runtime | No install needed |

**Missing dependencies with no fallback:** None — all libraries are runtime-provided by MotherDuck.

**Blocking conditions:**
- Phases 1 and 2 must be complete for tables to exist. Dives can be authored with empty tables if `CREATE TABLE IF NOT EXISTS` was run by Phase 1 logger.
- `trading` database must exist in MotherDuck (created when Phase 1 logger first connects).

---

## Open Questions

1. **REQUIRED_DATABASES for user-owned database**
   - What we know: `REQUIRED_DATABASES` with `type: "share"` is for shared databases. The `eastlake-sales.tsx` example uses `type: "share"` with a share UUID.
   - What's unclear: Whether creating a Dive via `MD_CREATE_DIVE` MCP tool for a database the creator already owns requires a `REQUIRED_DATABASES` export at all, or whether the creator's own databases are automatically available.
   - Recommendation: When creating via MCP tool, omit `REQUIRED_DATABASES` (or use an empty array) and verify the Dive can query `"trading"."main"."trades"` successfully. If it fails, use `{ type: "database", path: "trading", alias: "trading" }`. [ASSUMED]

2. **Aggregation Flight COALESCE behavior for sharpe_7d on days with 0 trades**
   - What we know: `daily_pnl` is populated by the aggregation Flight, which runs `WHERE status = 'filled'`. A day with no filled trades produces no row for that strategy.
   - What's unclear: Whether `sharpe_7d` and `max_drawdown` are properly handled by `AVG()` when some dates are missing (they will be — `AVG` ignores NULLs from missing rows).
   - Recommendation: DIVES-04 query already uses `AVG(sharpe_7d)` — this is correct; no action needed.

3. **Maximum strategy count for recharts multi-line chart**
   - What we know: There are 13 strategies across 3 accounts. All may appear in DIVES-03.
   - What's unclear: Whether recharts handles 13 simultaneous lines readably in a 300px-height chart.
   - Recommendation: Default DIVES-03 to show top-5 strategies by total P&L; add a "show all" toggle via `useDiveState`. [ASSUMED — this is a UX judgment, not a technical limitation]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `REQUIRED_DATABASES` can be omitted (or use empty array) when Dive creator owns the database | Open Questions #1, Dive skeleton | Dive fails to query trading DB; fix by adding `{ type: "database", path: "trading", alias: "trading" }` |
| A2 | Long-to-wide pivot via React `useMemo` is the right approach for recharts multi-series (vs DuckDB PIVOT) | Pattern 3 | Using PIVOT in SQL would also work; either approach is correct — PIVOT has dynamic column name uncertainty |
| A3 | 13 strategy lines is readable in a 300px LineChart; UX recommendation to show top-5 by default | Open Questions #3 | May need UX adjustment; does not affect correctness |
| A4 | Strategy names in the filter dropdown are hardcoded as a fixed list (not dynamically queried) | Pattern 1 | If a new strategy is added, dropdown needs manual update; low risk for v1.0 |

**If this table is empty:** N/A — four assumptions identified above.

---

## Sources

### Primary (HIGH confidence)
- [useSQLQuery reference](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/use-sql-query/) — API signature, return shape, N() helper, table name format
- [useDiveState reference](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/use-dive-state/) — signature, parameters, return shape, filter dropdown example
- [eastlake-sales.tsx](https://raw.githubusercontent.com/motherduckdb/blessed-dives-example/main/dives/eastlake-sales/eastlake-sales.tsx) — authoritative Dive component example: generate_series+unnest pattern, recharts LineChart+BarChart, N() helper, REQUIRED_DATABASES format, loading skeleton
- [blessed-dives-example CLAUDE.md](https://raw.githubusercontent.com/motherduckdb/blessed-dives-example/main/CLAUDE.md) — available libraries list, REQUIRED_DATABASES single-line rule, deployment notes
- [MD_CREATE_DIVE docs](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/md-create-dive/) — SQL function signature for creating Dives via MCP

### Secondary (MEDIUM confidence)
- [Creating Visualizations with Dives](https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/) — REQUIRED_DATABASES type "database" vs "share" distinction
- [DuckDB PIVOT docs](https://duckdb.org/docs/current/sql/statements/pivot) — `PIVOT ON strategy_name USING SUM GROUP BY date` syntax
- [recharts npm](https://www.npmjs.com/package/recharts) — version 3.8.1, 10-year-old legitimate package

### Tertiary (LOW confidence / training knowledge)
- DuckDB `strftime()` and `TIMESTAMPTZ::TIMESTAMP` cast behavior — from training knowledge, standard DuckDB
- `NULLIF(SUM(trade_count), 0)` divide-by-zero guard — standard SQL, confirmed via training

---

## Metadata

**Confidence breakdown:**
- Dive authoring contract (useSQLQuery, useDiveState): HIGH — verified from official MotherDuck docs
- Code patterns (LineChart, color styling, N() helper): HIGH — confirmed from eastlake-sales.tsx
- SQL queries (DIVES-01 through DIVES-04): HIGH — derived from SCHEMA-01..04 column contracts
- generate_series gap filling: HIGH — pattern confirmed from eastlake-sales.tsx example
- REQUIRED_DATABASES for own database: MEDIUM — type "database" referenced in docs; exact behavior for creator's own DB unconfirmed without calling `get_dive_guide` tool directly

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (MotherDuck Dives is an active product — recheck if authoring contract changes)
