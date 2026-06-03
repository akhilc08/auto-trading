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

// MotherDuck design-system tokens.
const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const GRID = "#e8e8e8";
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

// Multi-series line palette (14 entries) — index with i % LINE_COLORS.length.
const LINE_COLORS = [
  "#0777b3", "#bd4e35", "#2d7a00", "#e18727", "#638cad",
  "#990099", "#0099c6", "#dd4477", "#66aa00", "#b82e2e",
  "#316395", "#994499", "#22aa99", "#6633cc",
];

const usd = (v: unknown) =>
  N(v).toLocaleString("en-US", { style: "currency", currency: "USD" });

// Compact axis ticks: $1.2k / $3.4M.
const compactUsd = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
};

export default function EquityCurve() {
  // 90-day per-strategy cumulative P&L on a complete date spine.
  //
  // Gap-fill the *per-day* realized_pnl delta to 0 (no trades = no P&L change),
  // THEN compute the running SUM over the full spine. This keeps the cumulative
  // line flat across no-trade days (weekends/holidays) instead of collapsing it
  // to $0 — COALESCE on the cumulative value would produce a sawtooth (CR-01).
  // The CROSS JOIN spine guarantees one row per (date, strategy), so recharts
  // has no missing dates to gap.
  const { data, isLoading, isError } = useSQLQuery(`
    WITH date_spine AS (
      SELECT unnest(generate_series(
        current_date - INTERVAL 89 DAY,
        current_date,
        INTERVAL 1 DAY
      ))::DATE AS trade_date
    ),
    strategies AS (
      SELECT DISTINCT strategy_name
      FROM "trading"."main"."daily_pnl"
      WHERE date >= current_date - INTERVAL 89 DAY
    ),
    spine_cross AS (
      SELECT d.trade_date, s.strategy_name
      FROM date_spine d CROSS JOIN strategies s
    ),
    daily AS (
      SELECT
        sc.trade_date,
        sc.strategy_name,
        COALESCE(dp.realized_pnl, 0) AS realized_pnl
      FROM spine_cross sc
      LEFT JOIN "trading"."main"."daily_pnl" dp
        ON dp.date = sc.trade_date
        AND dp.strategy_name = sc.strategy_name
    )
    SELECT
      strftime(trade_date, '%Y-%m-%d') AS trade_date,
      strategy_name,
      SUM(realized_pnl) OVER (
        PARTITION BY strategy_name
        ORDER BY trade_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) AS cumulative_pnl
    FROM daily
    ORDER BY trade_date, strategy_name
  `);

  const rows = Array.isArray(data) ? data : [];

  // Pivot long-format rows (date, strategy, value) to wide format (one object
  // per date with each strategy as a key) — recharts needs wide. The SQL
  // already emits rows in (trade_date, strategy_name) order, so insertion order
  // is chronological; no JS re-sort needed.
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
      data: Object.values(byDate),
      strategies: Array.from(strategies),
    };
  }, [rows]);

  // KPIs: combined latest cumulative P&L across strategies, and strategy count.
  const last = chartData.data[chartData.data.length - 1] as
    | Record<string, number | string>
    | undefined;
  const combinedLatest = last
    ? chartData.strategies.reduce((acc, s) => acc + N(last[s]), 0)
    : 0;

  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>
            Equity Curve
          </h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Cumulative P&amp;L per strategy · last 90 days
          </p>
        </header>

        {/* KPI strip */}
        <div className="grid grid-cols-2 gap-8 mb-6" style={{ maxWidth: 440 }}>
          <div>
            {isLoading ? (
              <div className="h-8 w-28 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p
                className="text-3xl font-bold"
                style={{ ...numCell, color: combinedLatest >= 0 ? PNL_GREEN : PNL_RED }}
              >
                {usd(combinedLatest)}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Combined cumulative P&amp;L</p>
          </div>
          <div>
            {isLoading ? (
              <div className="h-8 w-12 bg-gray-200 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-bold" style={{ ...numCell, color: INK }}>
                {chartData.strategies.length}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: MUTED }}>Strategies</p>
          </div>
        </div>

        {isLoading ? (
          <div className="bg-gray-100 animate-pulse rounded" style={{ height: 300 }} />
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading equity curve.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: MUTED }}>
            No data yet — run a strategy to populate.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData.data} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis
                dataKey="trade_date"
                tick={{ fontSize: 11, fill: MUTED }}
                tickLine={false}
                axisLine={{ stroke: GRID }}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={compactUsd}
                tick={{ fontSize: 11, fill: MUTED }}
                tickLine={false}
                axisLine={false}
                width={56}
              />
              <Tooltip
                formatter={(v: number) => usd(v)}
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: `1px solid ${GRID}`,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                }}
                labelStyle={{ color: MUTED }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="plainline" />
              {chartData.strategies.map((s, i) => (
                <Line
                  key={s}
                  type="linear"
                  dataKey={s}
                  stroke={LINE_COLORS[i % LINE_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
