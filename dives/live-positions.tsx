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

  // KPIs derived from the loaded rows.
  const totalUnrealized = rows.reduce((acc, r) => acc + N(r.unrealized_pnl), 0);
  const distinctStrategies = new Set(rows.map((r) => String(r.strategy_name))).size;

  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>
            Live Positions
          </h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Latest snapshot per strategy
          </p>
        </header>

        {/* KPI strip */}
        <div className="grid grid-cols-3 gap-8 mb-6">
          <div>
            {isLoading ? (
              <div className="h-8 w-16 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {rows.length.toLocaleString()}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Open positions</p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-28 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p
                className="text-3xl font-bold"
                style={{ ...numCell, color: totalUnrealized >= 0 ? PNL_GREEN : PNL_RED }}
              >
                {usd(totalUnrealized)}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Total unrealized P&amp;L</p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-12 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {distinctStrategies}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Strategies</p>
          </div>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
          </div>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading positions.</p>
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
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Symbol</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Qty</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Avg Entry</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Current</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Unrealized P&amp;L</th>
                <th className="py-2 text-left text-xs font-semibold" style={{ color: MUTED }}>Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={i}
                  className="transition-colors hover:bg-gray-100"
                  style={{ borderBottom: `1px solid ${ROW_RULE}` }}
                >
                  <td className="py-1.5 pr-4 font-medium">{String(r.symbol)}</td>
                  <td className="py-1.5 pr-4" style={{ color: MUTED }}>{String(r.strategy_name)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{N(r.qty).toLocaleString()}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{usd(r.avg_entry_price)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{usd(r.current_price)}</td>
                  <td
                    className="py-1.5 pr-4 text-right font-medium"
                    style={{ ...numCell, color: N(r.unrealized_pnl) >= 0 ? PNL_GREEN : PNL_RED }}
                  >
                    {usd(r.unrealized_pnl)}
                  </td>
                  <td className="py-1.5" style={{ color: MUTED }}>{String(r.snapshot_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
