import { useDiveState, useSQLQuery } from "@motherduck/react-sql-query";

// DuckDB returns BIGINT/DECIMAL as BigInt/objects — wrap every numeric value.
const N = (v: unknown): number => (v != null ? Number(v) : 0);

// Color-coded P&L (inline style only — never Tailwind bracket syntax).
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

// Closed allow-list — mirror of core/accounts.py _ACCOUNT_STRATEGIES.
// The filter value must be one of these (or "all") before it is interpolated
// into SQL. Never interpolate raw user/URL input (T-3-01 injection mitigation).
const STRATEGIES = [
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

export default function TradeLog() {
  const [strategy, setStrategy] = useDiveState<string>("strategy", "all");

  // Only interpolate a value that is in the closed allow-list; anything else
  // (including "all" or a tampered URL value) falls back to no filter.
  const whereClause =
    strategy !== "all" && STRATEGIES.includes(strategy)
      ? `AND strategy_name = '${strategy}'`
      : "";

  const { data, isLoading, isError } = useSQLQuery(`
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
      ${whereClause}
    ORDER BY submitted_at DESC
    LIMIT 500
  `);

  const rows = Array.isArray(data) ? data : [];

  return (
    <div className="p-6" style={{ background: "#f8f8f8" }}>
      <h1 className="text-2xl font-semibold" style={{ color: "#231f20" }}>
        Trade Log
      </h1>
      <p className="text-sm mb-4" style={{ color: "#6a6a6a" }}>
        Trades over the last 90 days
      </p>

      <div className="mb-4">
        <label className="text-sm mr-2" style={{ color: "#6a6a6a" }}>
          Strategy
        </label>
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          className="text-sm border rounded px-2 py-1"
          style={{ color: "#231f20" }}
        >
          <option value="all">All strategies</option>
          {STRATEGIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      ) : isError ? (
        <p style={{ color: PNL_RED }}>Error loading trades.</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6a6a6a" }}>No data yet — run a strategy to populate.</p>
      ) : (
        <table className="text-sm w-full" style={{ color: "#231f20" }}>
          <thead>
            <tr className="text-left" style={{ color: "#6a6a6a" }}>
              <th className="py-1 pr-4">Symbol</th>
              <th className="py-1 pr-4">Side</th>
              <th className="py-1 pr-4 text-right">Qty</th>
              <th className="py-1 pr-4">Submitted</th>
              <th className="py-1 pr-4 text-right">Fill Price</th>
              <th className="py-1 pr-4 text-right">PnL</th>
              <th className="py-1 pr-4">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="py-1 pr-4">{String(r.symbol)}</td>
                <td className="py-1 pr-4">{String(r.side)}</td>
                <td className="py-1 pr-4 text-right">{N(r.qty)}</td>
                <td className="py-1 pr-4">{String(r.submitted_at)}</td>
                <td className="py-1 pr-4 text-right">
                  {N(r.filled_avg_price).toFixed(2)}
                </td>
                <td
                  className="py-1 pr-4 text-right"
                  style={{ color: N(r.pnl) >= 0 ? PNL_GREEN : PNL_RED }}
                >
                  {N(r.pnl).toFixed(2)}
                </td>
                <td className="py-1 pr-4">{String(r.strategy_name)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
