import { useMemo } from "react";
import { useSQLQuery } from "@motherduck/react-sql-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// DuckDB returns BIGINT/DECIMAL as BigInt/objects — wrap every numeric value.
const N = (v: unknown): number => (v != null ? Number(v) : 0);

// Multi-series line palette (14 entries) — index with i % LINE_COLORS.length.
const LINE_COLORS = [
  "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099",
  "#0099c6", "#dd4477", "#66aa00", "#b82e2e", "#316395",
  "#994499", "#22aa99", "#aaaa11", "#6633cc",
];

export default function EquityCurve() {
  // 90-day per-strategy cumulative P&L on a complete date spine. The
  // date_spine CROSS JOIN strategies LEFT JOIN cumulative-P&L with
  // COALESCE(...,0) guarantees one row per (date, strategy) so the recharts
  // lines have no time-axis gaps (recharts does not interpolate missing dates).
  const { data, isLoading, isError } = useSQLQuery(`
    WITH date_spine AS (
      SELECT unnest(generate_series(
        current_date - INTERVAL 89 DAY,
        current_date,
        INTERVAL 1 DAY
      ))::DATE AS trade_date
    ),
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
  `);

  const rows = Array.isArray(data) ? data : [];

  // Pivot long-format rows (date, strategy, value) to wide format
  // (one object per date with each strategy as a key) — recharts needs wide.
  const chartData = useMemo(() => {
    const byDate: Record<string, Record<string, number | string>> = {};
    const strategies = new Set<string>();
    for (const r of rows) {
      const date = String(r.trade_date);
      const strat = String(r.strategy_name);
      if (!byDate[date]) byDate[date] = { trade_date: date };
      byDate[date][strat] = N(r.cumulative_pnl);
      strategies.add(strat);
    }
    return {
      data: Object.values(byDate).sort((a, b) =>
        String(a.trade_date) > String(b.trade_date) ? 1 : -1
      ),
      strategies: Array.from(strategies),
    };
  }, [rows]);

  return (
    <div className="p-6" style={{ background: "#f8f8f8" }}>
      <h1 className="text-2xl font-semibold" style={{ color: "#231f20" }}>
        Equity Curve
      </h1>
      <p className="text-sm mb-4" style={{ color: "#6a6a6a" }}>
        Cumulative P&amp;L per strategy over the last 90 days
      </p>

      {isLoading ? (
        <div
          className="bg-gray-100 animate-pulse rounded"
          style={{ height: 300 }}
        />
      ) : isError ? (
        <p style={{ color: "#bc1200" }}>Error loading equity curve.</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#6a6a6a" }}>No data yet — run a strategy to populate.</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="trade_date" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`$${N(v).toFixed(2)}`, ""]} />
            <Legend />
            {chartData.strategies.map((s, i) => (
              <Line
                key={s}
                type="linear"
                dataKey={s}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
