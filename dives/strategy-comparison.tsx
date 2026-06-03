import { useSQLQuery } from "@motherduck/react-sql-query";

// DuckDB returns BIGINT/DECIMAL as BigInt/objects — wrap every numeric value.
const N = (v: unknown): number => (v != null ? Number(v) : 0);

// MotherDuck design-system tokens.
const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const RULE = "#e4e4e4";
const ROW_RULE = "#efefef";
// Color-coded P&L (inline style only — never Tailwind bracket syntax).
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

const usd = (v: unknown) =>
  N(v).toLocaleString("en-US", { style: "currency", currency: "USD" });

export default function StrategyComparison() {
  // One row per strategy. sharpe_7d / max_drawdown are read straight from
  // daily_pnl (pre-computed by the Phase 2 aggregation Flight) — never
  // recomputed here. NULLIF(SUM(trade_count), 0) guards the win-rate ratio
  // against divide-by-zero.
  const { data, isLoading, isError } = useSQLQuery(`
    SELECT
      strategy_name,
      ROUND(AVG(sharpe_7d), 3)                                        AS sharpe_7d,
      ROUND(MIN(max_drawdown), 4)                                     AS max_drawdown,
      ROUND(100.0 * SUM(win_count) / NULLIF(SUM(trade_count), 0), 1)  AS win_rate_pct,
      SUM(trade_count)                                                AS trade_count,
      ROUND(SUM(realized_pnl), 2)                                     AS total_pnl
    FROM "trading"."main"."daily_pnl"
    GROUP BY strategy_name
    ORDER BY total_pnl DESC
  `);

  const rows = Array.isArray(data) ? data : [];

  // NULL-tolerant numeric formatter (sharpe/drawdown are NULL when the
  // aggregation Flight had insufficient history) — render "—", never NaN.
  const fmt = (v: unknown, digits: number) =>
    v == null ? "—" : N(v).toFixed(digits);
  const pct = (v: unknown) => (v == null ? "—" : `${N(v).toFixed(1)}%`);

  // KPIs derived from the loaded rows.
  const combinedPnl = rows.reduce((acc, r) => acc + N(r.total_pnl), 0);

  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>
            Strategy Comparison
          </h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Risk and return per strategy · ranked by total P&amp;L
          </p>
        </header>

        {/* KPI strip */}
        <div className="grid grid-cols-2 gap-8 mb-6" style={{ maxWidth: 440 }}>
          <div>
            {isLoading ? (
              <div className="h-8 w-12 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {rows.length}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Strategies</p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-28 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p
                className="text-3xl font-bold"
                style={{ ...numCell, color: combinedPnl >= 0 ? PNL_GREEN : PNL_RED }}
              >
                {usd(combinedPnl)}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Combined P&amp;L</p>
          </div>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
          </div>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading strategy metrics.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: MUTED }}>
            No data yet — run a strategy to populate.
          </p>
        ) : (
          <table
            className="w-full text-sm"
            style={{ borderCollapse: "collapse", color: INK }}
          >
            <thead>
              <tr style={{ borderBottom: `1px solid ${RULE}` }}>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Sharpe 7d</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Max Drawdown</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Win Rate</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Trades</th>
                <th className="py-2 text-right text-xs font-semibold" style={{ color: MUTED }}>Total P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={i}
                  className="transition-colors hover:bg-gray-100"
                  style={{ borderBottom: `1px solid ${ROW_RULE}` }}
                >
                  <td className="py-1.5 pr-4 font-medium">{String(r.strategy_name)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{fmt(r.sharpe_7d, 3)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{fmt(r.max_drawdown, 4)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{pct(r.win_rate_pct)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{N(r.trade_count).toLocaleString()}</td>
                  <td
                    className="py-1.5 text-right font-medium"
                    style={{ ...numCell, color: N(r.total_pnl) >= 0 ? PNL_GREEN : PNL_RED }}
                  >
                    {usd(r.total_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
