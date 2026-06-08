import { useSQLQuery } from "@motherduck/react-sql-query";

const N = (v: unknown): number => (v != null ? Number(v) : 0);

const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const RULE = "#e4e4e4";
const ROW_RULE = "#efefef";
const PNL_RED = "#bc1200";
const WARN = "#b8860b";

export default function RiskAlerts() {
  // Today's active alerts only. risk_alerts is upserted by the risk-monitor Flight.
  const { data, isLoading, isError } = useSQLQuery(`
    SELECT
      account_name,
      strategy_name,
      alert_type,
      severity,
      ROUND(metric_value, 4) AS metric_value,
      ROUND(threshold, 4)    AS threshold,
      detail,
      strftime(computed_at, '%Y-%m-%d %H:%M') AS computed_at
    FROM "trading"."main"."risk_alerts"
    WHERE alert_date = (now() AT TIME ZONE 'America/New_York')::DATE
    ORDER BY CASE severity WHEN 'breach' THEN 0 ELSE 1 END, account_name, alert_type
  `);

  const rows = Array.isArray(data) ? data : [];
  const color = (sev: unknown) => (String(sev) === "breach" ? PNL_RED : WARN);
  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>Risk Alerts</h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Active limit breaches · today · breaches first
          </p>
        </header>

        {isLoading ? (
          <p style={{ color: MUTED }}>Loading…</p>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading risk alerts.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: "#2d7a00" }}>
            All clear — no active risk-limit breaches today.
          </p>
        ) : (
          <table className="w-full text-sm" style={{ borderCollapse: "collapse", color: INK }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${RULE}` }}>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Account</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Type</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Severity</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Detail</th>
                <th className="py-2 text-right text-xs font-semibold" style={{ color: MUTED }}>As of</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${ROW_RULE}` }}>
                  <td className="py-1.5 pr-4 font-medium">{String(r.account_name)}</td>
                  <td className="py-1.5 pr-4">{String(r.strategy_name) || "—"}</td>
                  <td className="py-1.5 pr-4">{String(r.alert_type)}</td>
                  <td className="py-1.5 pr-4 font-semibold" style={{ color: color(r.severity) }}>
                    {String(r.severity)}
                  </td>
                  <td className="py-1.5 pr-4">{String(r.detail)}</td>
                  <td className="py-1.5 text-right" style={numCell}>{String(r.computed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
