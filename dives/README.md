# Dives — Phase 3

Four interactive [MotherDuck Dives](https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/)
over the live trade and performance data written by Phases 1 and 2.

## Deliverable model

Each Dive is BOTH:

1. A versioned **`dives/*.tsx`** file committed in this repo (for review and history), and
2. A **live Dive created in MotherDuck via the MCP tools** (`create_dive` / `save_dive`,
   updated via `edit_dive_content`). Dives live in the MotherDuck workspace, not a local server.

There is **no npm install** for the Dives themselves: the Dive runtime bundles `react`,
`recharts`, `lucide-react`, and `@motherduck/react-sql-query`. Do not import anything else.
`dives/_conventions.tsx` is a reference/snippets file the four Dive authors copy from — it is
**never deployed** as a Dive itself.

## File → Dive map

| File | Requirement | Live Dive | Reads |
|------|-------------|-----------|-------|
| `dives/trade-log.tsx` | DIVES-01 | `trade-log` | `"trading"."main"."trades"` |
| `dives/live-positions.tsx` | DIVES-02 | `live-positions` | `"trading"."main"."positions"` |
| `dives/equity-curve.tsx` | DIVES-03 | `equity-curve` | `"trading"."main"."daily_pnl"` |
| `dives/strategy-comparison.tsx` | DIVES-04 | `strategy-comparison` | `"trading"."main"."daily_pnl"` |

## Hard conventions (see `_conventions.tsx`)

- Table refs are always fully qualified and double-quoted: `"trading"."main"."trades"`.
- Wrap every numeric value with `N()` (DuckDB returns BIGINT/DECIMAL as BigInt/objects).
- Custom colors via inline `style={{}}` only — never Tailwind bracket syntax (`text-[#hex]`).
  Positive P&L `#2d7a00`, negative `#bc1200`.
- Every Dive must render `"No data yet — run a strategy to populate."` on empty tables rather
  than crashing — Phases 1/2 may be unshipped, so tables can be empty.
- Format dates in SQL with `strftime()`, never JS `Date`.

## REQUIRED_DATABASES fallback decision

When creating a Dive via the MCP `create_dive`/`save_dive` tool, **omit** `REQUIRED_DATABASES` —
the creator owns the `trading` database so it is automatically available (confirmed by the Dive
authoring guide and the Wave 0 gate). Only if a saved Dive fails to query `"trading"."main".*`
with a missing-catalog error, add the single line (it must stay one line) and `save_dive` again:

```tsx
export const REQUIRED_DATABASES = [{ type: "database", path: "trading", alias: "trading" }];
```

## SQL pre-flight block (Wave 0 gate)

Run via the MotherDuck MCP `query` tool before authoring Dives — confirms the tables resolve
against the live `trading` DB (counts may be `0`; empty is fine):

```sql
-- Tables exist and (optionally) have data
SELECT 'trades' AS tbl, COUNT(*) AS rows FROM "trading"."main"."trades"
UNION ALL
SELECT 'positions', COUNT(*) FROM "trading"."main"."positions"
UNION ALL
SELECT 'daily_pnl', COUNT(*) FROM "trading"."main"."daily_pnl";

-- Latest positions snapshot is present (NULL acceptable if empty)
SELECT MAX(snapshot_at) AS latest_snapshot FROM "trading"."main"."positions";

-- daily_pnl has data for recent dates (zero rows acceptable if empty)
SELECT date, COUNT(*) AS strategy_count FROM "trading"."main"."daily_pnl"
WHERE date >= current_date - 7
GROUP BY date ORDER BY date DESC;
```

**Wave 0 result (2026-06-03):** all four tables resolve; `trades`/`positions`/`daily_pnl` are
empty (0 rows) — expected, Phases 1/2 have not logged live trades yet. MCP `query` and
`save_dive`/`create_dive` confirmed reachable. `REQUIRED_DATABASES` not needed.
