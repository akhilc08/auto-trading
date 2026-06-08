import { useSQLQuery } from "@motherduck/react-sql-query";

const N = (v: unknown): number => (v != null ? Number(v) : 0);

const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const RULE = "#e4e4e4";
const ROW_RULE = "#efefef";
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

export default function AlphaBeta() {
  // Regress each strategy's daily return on SPY's daily return.
  // strat_ret = realized_pnl / (that day's latest equity); spy_ret = SPY close pct-change.
  const { data, isLoading, isError } = useSQLQuery(`
    WITH spy AS (
      SELECT date,
             close / lag(close) OVER (ORDER BY date) - 1 AS spy_ret
      FROM "trading"."main"."benchmark_prices"
      WHERE symbol = 'SPY'
    ),
    eq AS (
      SELECT strategy_name, account_name, d, equity FROM (
        SELECT strategy_name, account_name,
               (snapshot_at AT TIME ZONE 'America/New_York')::DATE AS d,
               equity,
               ROW_NUMBER() OVER (
                 PARTITION BY strategy_name, account_name,
                              (snapshot_at AT TIME ZONE 'America/New_York')::DATE
                 ORDER BY snapshot_at DESC) AS rn
        FROM "trading"."main"."portfolio_snapshots"
        WHERE equity IS NOT NULL AND equity > 0
      ) WHERE rn = 1
    ),
    strat AS (
      SELECT p.strategy_name, p.date,
             p.realized_pnl / eq.equity AS strat_ret
      FROM "trading"."main"."daily_pnl" p
      JOIN eq ON eq.strategy_name = p.strategy_name
             AND eq.account_name = p.account_name
             AND eq.d = p.date
      WHERE p.realized_pnl IS NOT NULL
    ),
    joined AS (
      SELECT strat.strategy_name, strat.strat_ret, spy.spy_ret
      FROM strat JOIN spy ON spy.date = strat.date
      WHERE spy.spy_ret IS NOT NULL
    )
    SELECT
      strategy_name,
      COUNT(*)                                              AS n_days,
      ROUND(regr_slope(strat_ret, spy_ret), 3)             AS beta,
      ROUND(regr_intercept(strat_ret, spy_ret) * 252, 4)   AS alpha_annual
    FROM joined
    GROUP BY strategy_name
    HAVING COUNT(*) >= 2
    ORDER BY strategy_name
  `);

  const rows = Array.isArray(data) ? data : [];
  const fmt = (v: unknown, d: number) => (v == null ? "—" : N(v).toFixed(d));
  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>Alpha / Beta vs SPY</h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Daily-return regression on SPY · alpha annualized (×252)
          </p>
        </header>

        {isLoading ? (
          <p style={{ color: MUTED }}>Loading…</p>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading alpha/beta.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: MUTED }}>
            No data yet — load benchmark prices and accrue daily P&amp;L to populate.
          </p>
        ) : (
          <table className="w-full text-sm" style={{ borderCollapse: "collapse", color: INK }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${RULE}` }}>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Beta</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Alpha (ann.)</th>
                <th className="py-2 text-right text-xs font-semibold" style={{ color: MUTED }}>Days</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${ROW_RULE}` }}>
                  <td className="py-1.5 pr-4 font-medium">{String(r.strategy_name)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{fmt(r.beta, 3)}</td>
                  <td className="py-1.5 pr-4 text-right" style={{ ...numCell, color: r.alpha_annual == null ? MUTED : N(r.alpha_annual) >= 0 ? PNL_GREEN : PNL_RED }}>
                    {fmt(r.alpha_annual, 4)}
                  </td>
                  <td className="py-1.5 text-right" style={numCell}>{N(r.n_days).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
