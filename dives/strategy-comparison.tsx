import { useSQLQuery } from "@motherduck/react-sql-query";

// DuckDB returns BIGINT/DECIMAL as BigInt/objects — wrap every numeric value.
const N = (v: unknown): number => (v != null ? Number(v) : 0);

// Color-coded P&L (inline style only — never Tailwind bracket syntax).
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

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

  return (
    <div className="p-6" style={{ background: "#f8f8f8" }}>
      <h1 className="text-2xl font-semibold" style={{ color: "#231f20" }}>
        Strategy Comparison
      </h1>
      <p className="text-sm mb-4" style={{ color: "#6a6a6a" }}>
        Risk and return metrics per strategy
      </p>

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      ) : isError ? (
        <p style={{ color: PNL_RED }}>Error loading strategy metrics.</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6a6a6a" }}>No data yet — run a strategy to populate.</p>
      ) : (
        <table className="text-sm w-full" style={{ color: "#231f20" }}>
          <thead>
            <tr className="text-left" style={{ color: "#6a6a6a" }}>
              <th className="py-1 pr-4">Strategy</th>
              <th className="py-1 pr-4 text-right">Sharpe 7d</th>
              <th className="py-1 pr-4 text-right">Max Drawdown</th>
              <th className="py-1 pr-4 text-right">Win Rate %</th>
              <th className="py-1 pr-4 text-right">Trade Count</th>
              <th className="py-1 pr-4 text-right">Total P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="py-1 pr-4">{String(r.strategy_name)}</td>
                <td className="py-1 pr-4 text-right">{fmt(r.sharpe_7d, 3)}</td>
                <td className="py-1 pr-4 text-right">{fmt(r.max_drawdown, 4)}</td>
                <td className="py-1 pr-4 text-right">{fmt(r.win_rate_pct, 1)}</td>
                <td className="py-1 pr-4 text-right">{N(r.trade_count)}</td>
                <td
                  className="py-1 pr-4 text-right"
                  style={{ color: N(r.total_pnl) >= 0 ? PNL_GREEN : PNL_RED }}
                >
                  {N(r.total_pnl).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
