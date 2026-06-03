import { useSQLQuery } from "@motherduck/react-sql-query";

// DuckDB returns BIGINT/DECIMAL as BigInt/objects — wrap every numeric value.
const N = (v: unknown): number => (v != null ? Number(v) : 0);

// Color-coded P&L (inline style only — never Tailwind bracket syntax).
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

export default function LivePositions() {
  // Latest snapshot per strategy: pick MAX(snapshot_at) per strategy_name,
  // then join back to positions on (strategy_name, snapshot_at).
  const { data, isLoading, isError } = useSQLQuery(`
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
  `);

  const rows = Array.isArray(data) ? data : [];

  return (
    <div className="p-6" style={{ background: "#f8f8f8" }}>
      <h1 className="text-2xl font-semibold" style={{ color: "#231f20" }}>
        Live Positions
      </h1>
      <p className="text-sm mb-4" style={{ color: "#6a6a6a" }}>
        Latest open positions per strategy with unrealized P&amp;L
      </p>

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      ) : isError ? (
        <p style={{ color: PNL_RED }}>Error loading positions.</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6a6a6a" }}>No data yet — run a strategy to populate.</p>
      ) : (
        <table className="text-sm w-full" style={{ color: "#231f20" }}>
          <thead>
            <tr className="text-left" style={{ color: "#6a6a6a" }}>
              <th className="py-1 pr-4">Symbol</th>
              <th className="py-1 pr-4">Strategy</th>
              <th className="py-1 pr-4 text-right">Qty</th>
              <th className="py-1 pr-4 text-right">Avg Entry</th>
              <th className="py-1 pr-4 text-right">Current</th>
              <th className="py-1 pr-4 text-right">Unrealized P&amp;L</th>
              <th className="py-1 pr-4">Snapshot</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="py-1 pr-4">{String(r.symbol)}</td>
                <td className="py-1 pr-4">{String(r.strategy_name)}</td>
                <td className="py-1 pr-4 text-right">{N(r.qty)}</td>
                <td className="py-1 pr-4 text-right">
                  {N(r.avg_entry_price).toFixed(2)}
                </td>
                <td className="py-1 pr-4 text-right">
                  {N(r.current_price).toFixed(2)}
                </td>
                <td
                  className="py-1 pr-4 text-right"
                  style={{
                    color: N(r.unrealized_pnl) >= 0 ? PNL_GREEN : PNL_RED,
                  }}
                >
                  {N(r.unrealized_pnl).toFixed(2)}
                </td>
                <td className="py-1 pr-4">{String(r.snapshot_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
