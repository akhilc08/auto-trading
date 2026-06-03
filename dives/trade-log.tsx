import { useDiveState, useSQLQuery } from "@motherduck/react-sql-query";

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

  // T-3-01: only interpolate a value from the closed allow-list AND matching a
  // strict identifier pattern. The regex keeps safety local to the interpolation
  // site (defense-in-depth) rather than depending on allow-list contents — if a
  // future strategy name ever contained a quote/metacharacter it still cannot
  // reach the SQL. Anything else (incl. "all" or a tampered URL value) → no filter.
  const isSafeStrategy =
    strategy !== "all" &&
    STRATEGIES.includes(strategy) &&
    /^[a-z0-9_]+$/.test(strategy);
  const whereClause = isSafeStrategy
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

  // KPIs derived from the loaded rows (the shown set — last 90 days, max 500).
  const netPnl = rows.reduce((acc, r) => acc + N(r.pnl), 0);
  const distinctStrategies = new Set(rows.map((r) => String(r.strategy_name))).size;

  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="flex items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-xl font-semibold" style={{ color: INK }}>
              Trade Log
            </h1>
            <p className="text-sm" style={{ color: MUTED }}>
              Last 90 days{isSafeStrategy ? ` · ${strategy}` : ""} · newest first
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm" style={{ color: MUTED }}>
            Strategy
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="text-sm rounded px-2 py-1"
              style={{ color: INK, border: `1px solid ${RULE}`, background: "#fff" }}
            >
              <option value="all">All strategies</option>
              {STRATEGIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </header>

        {/* KPI strip */}
        <div className="grid grid-cols-3 gap-8 mb-6">
          <div>
            {isLoading ? (
              <div className="h-8 w-20 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {rows.length.toLocaleString()}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>
              Trades shown
            </p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-28 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p
                className="text-3xl font-bold"
                style={{ ...numCell, color: netPnl >= 0 ? PNL_GREEN : PNL_RED }}
              >
                {usd(netPnl)}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>
              Net P&amp;L (shown)
            </p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-12 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {distinctStrategies}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>
              Strategies
            </p>
          </div>
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
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Side</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Qty</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Submitted</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Fill Price</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>PnL</th>
                <th className="py-2 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
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
                  <td className="py-1.5 pr-4" style={{ color: MUTED }}>{String(r.side)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{N(r.qty).toLocaleString()}</td>
                  <td className="py-1.5 pr-4" style={{ color: MUTED }}>{String(r.submitted_at)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{usd(r.filled_avg_price)}</td>
                  <td
                    className="py-1.5 pr-4 text-right font-medium"
                    style={{ ...numCell, color: N(r.pnl) >= 0 ? PNL_GREEN : PNL_RED }}
                  >
                    {usd(r.pnl)}
                  </td>
                  <td className="py-1.5" style={{ color: MUTED }}>{String(r.strategy_name)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
