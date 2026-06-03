/**
 * dives/_conventions.tsx — SHARED AUTHORING REFERENCE (NOT a deployed Dive).
 *
 * The four Phase 3 Dive authors (trade-log, live-positions, equity-curve,
 * strategy-comparison) COPY the pieces below into their own .tsx files. The
 * MotherDuck Dive runtime cannot import across files, so each Dive must inline
 * the helpers/constants it uses — this file is the single source of truth they
 * copy from, so the four Dives cannot diverge on colors, BigInt handling,
 * empty-state text, table-name format, or the injection-safe strategy filter.
 *
 * Source of patterns: .planning/phases/03-dives/03-RESEARCH.md and the live
 * MotherDuck Dive authoring guide (get_dive_guide).
 */

// ---------------------------------------------------------------------------
// Numeric helper — REQUIRED on every numeric cell.
// DuckDB returns BIGINT/HUGEINT/DECIMAL as JS BigInt / special objects that
// crash when rendered in JSX or passed to .toFixed(). Always wrap with N().
// ---------------------------------------------------------------------------
export const N = (v: unknown): number => (v != null ? Number(v) : 0);

// ---------------------------------------------------------------------------
// Color constants (exact hex from DIVES-02 + the MotherDuck design system).
// Apply colors ONLY via inline style: style={{ color: PNL_GREEN }}.
// NEVER use Tailwind bracket syntax (text-[#2d7a00] / bg-[#bc1200]) — the Dive
// runtime cannot resolve arbitrary Tailwind values and the styling silently
// fails (03-RESEARCH.md Pitfall 2).
// ---------------------------------------------------------------------------
export const PNL_GREEN = "#2d7a00"; // positive P&L
export const PNL_RED = "#bc1200"; // negative P&L

// Multi-series line palette for DIVES-03 (recharts), 14 entries
// (03-RESEARCH.md Pattern 3). Index with LINE_COLORS[i % LINE_COLORS.length].
export const LINE_COLORS = [
  "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099",
  "#0099c6", "#dd4477", "#66aa00", "#b82e2e", "#316395",
  "#994499", "#22aa99", "#aaaa11", "#6633cc",
];

// ---------------------------------------------------------------------------
// STRATEGIES — the CLOSED strategy allow-list.
// Mirror of core/accounts.py _ACCOUNT_STRATEGIES (the strategies that actually
// run and log to "trading"."main"."trades"). The DIVES-01 filter dropdown is
// built ONLY from these values plus "all"; the selected value must be one of
// these (or "all") before it is interpolated into SQL — never interpolate raw
// user/URL input. This is the T-3-01 SQL-injection mitigation.
//
//   stat_arb account:    stat_arb, stat_arb_v2, stat_arb_v3,
//                        market_neutral, market_neutral_v2
//   macro_vol account:   trend_following, trend_following_v2,
//                        regime_switching, vol_risk_premium
//   stock_alpha account: multi_factor_equity, multi_factor_equity_v2,
//                        post_earnings_drift
// ---------------------------------------------------------------------------
export const STRATEGIES = [
  "stat_arb",
  "stat_arb_v2",
  "stat_arb_v3",
  "market_neutral",
  "market_neutral_v2",
  "trend_following",
  "trend_following_v2",
  "regime_switching",
  "vol_risk_premium",
  "multi_factor_equity",
  "multi_factor_equity_v2",
  "post_earnings_drift",
];

/* ===========================================================================
 * DIVE SKELETON (copy/adapt — do not import).
 *
 * import { useSQLQuery } from "@motherduck/react-sql-query";
 *
 * const N = (v: unknown): number => (v != null ? Number(v) : 0);
 *
 * export default function MyDive() {
 *   const { data, isLoading, isError } = useSQLQuery(`
 *     SELECT ... FROM "trading"."main"."<table>"
 *   `);
 *
 *   // data IS the rows array — there is NO data.rows. Always guard:
 *   const rows = Array.isArray(data) ? data : [];
 *
 *   if (isLoading) return <p>Loading…</p>;
 *   if (isError)   return <p>Error loading data.</p>;
 *   if (rows.length === 0) return <p>No data yet — run a strategy to populate.</p>;
 *
 *   return <div>…</div>;
 * }
 *
 * HARD RULES (all four Dives):
 *   - Table refs are ALWAYS fully qualified + double-quoted:
 *       "trading"."main"."trades" / "positions" / "daily_pnl"
 *   - Empty state text is exactly: "No data yet — run a strategy to populate."
 *     (tables may be empty — Phases 1/2 may be unshipped; never crash).
 *   - Wrap every numeric value with N() before .toFixed()/render.
 *   - Format dates in SQL with strftime(), never JS Date.
 *   - Custom colors via inline style={{}}, never Tailwind bracket classes.
 *
 * REQUIRED_DATABASES: OMIT when creating the Dive via the MotherDuck MCP
 * save_dive tool — the creator owns the "trading" DB so it is auto-available
 * (confirmed by the Dive guide + Wave 0 gate). Only if a saved Dive fails to
 * query "trading" add the single line (must stay one line):
 *   export const REQUIRED_DATABASES = [{ type: "database", path: "trading", alias: "trading" }];
 * =========================================================================== */
