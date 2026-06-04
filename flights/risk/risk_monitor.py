"""risk-monitor Flight.

Reads the latest positions / portfolio / drawdown data and writes risk-limit breaches to
trading.main.risk_alerts. Pure MotherDuck SQL + Python; only MOTHERDUCK_TOKEN is needed
(no Alpaca credentials, no secret). Intended to run intraday during market hours.

SELF-CONTAINED: MotherDuck Flights run a single source file, so this module imports nothing
from the rest of the repo — thresholds are inlined below.

Account-level metrics dedupe the per-strategy-duplicated snapshot rows: flights/exec/_runner.py
snapshots the same account-wide Alpaca positions/equity once per strategy, so
positions/portfolio_snapshots rows repeat across strategy_name. Taking the most recent row per
(account, symbol) / per account recovers the true account view.
"""
from datetime import datetime, timezone

import duckdb

# ── Risk limits (fraction of equity; ascending warn < breach) ──────────────────────────────
GROSS_EXPOSURE_WARN = 1.5    # gross exposure / equity
GROSS_EXPOSURE_BREACH = 2.0
CONCENTRATION_WARN = 0.25    # largest single position / equity
CONCENTRATION_BREACH = 0.40
DRAWDOWN_WARN = 0.05         # max_drawdown (dollars) / equity
DRAWDOWN_BREACH = 0.10

DDL = """
CREATE TABLE IF NOT EXISTS trading.main.risk_alerts (
    alert_date    DATE NOT NULL,
    account_name  VARCHAR NOT NULL,
    strategy_name VARCHAR NOT NULL,
    alert_type    VARCHAR NOT NULL,
    severity      VARCHAR NOT NULL,
    metric_value  DECIMAL(18,6),
    threshold     DECIMAL(18,6),
    detail        VARCHAR,
    computed_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (alert_date, account_name, strategy_name, alert_type)
)
"""

# Latest row per (account, symbol) across ALL strategies (dedupes the per-strategy duplication).
_LATEST_POSITIONS = """
SELECT account_name, symbol, qty, current_price FROM (
    SELECT account_name, symbol, qty, current_price,
           ROW_NUMBER() OVER (PARTITION BY account_name, symbol ORDER BY snapshot_at DESC) AS rn
    FROM trading.main.positions
    WHERE current_price IS NOT NULL
) WHERE rn = 1
"""

# Latest equity per account.
_LATEST_EQUITY = """
SELECT account_name, equity FROM (
    SELECT account_name, equity,
           ROW_NUMBER() OVER (PARTITION BY account_name ORDER BY snapshot_at DESC) AS rn
    FROM trading.main.portfolio_snapshots
    WHERE equity IS NOT NULL
) WHERE rn = 1
"""

# Latest max_drawdown (dollars) per (strategy, account) from daily_pnl.
_LATEST_DRAWDOWN = """
SELECT strategy_name, account_name, max_drawdown FROM (
    SELECT strategy_name, account_name, max_drawdown,
           ROW_NUMBER() OVER (PARTITION BY strategy_name, account_name ORDER BY date DESC) AS rn
    FROM trading.main.daily_pnl
    WHERE max_drawdown IS NOT NULL
) WHERE rn = 1
"""

_UPSERT_ALERT = """
INSERT INTO trading.main.risk_alerts
    (alert_date, account_name, strategy_name, alert_type, severity, metric_value,
     threshold, detail, computed_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (alert_date, account_name, strategy_name, alert_type) DO UPDATE SET
    severity = EXCLUDED.severity,
    metric_value = EXCLUDED.metric_value,
    threshold = EXCLUDED.threshold,
    detail = EXCLUDED.detail,
    computed_at = EXCLUDED.computed_at
"""


def _account_metrics(con):
    """Per-account exposure metrics. Returns
    {account: {gross_ratio, concentration, top_symbol, equity}}."""
    equity = {a: float(e) for a, e in con.execute(_LATEST_EQUITY).fetchall()}
    positions = con.execute(_LATEST_POSITIONS).fetchall()
    gross = {}      # account -> total |market value|
    top = {}        # account -> (symbol, market value)
    for account, symbol, qty, price in positions:
        mv = abs(float(qty) * float(price))
        gross[account] = gross.get(account, 0.0) + mv
        if account not in top or mv > top[account][1]:
            top[account] = (symbol, mv)
    out = {}
    for account, g in gross.items():
        eq = equity.get(account, 0.0)
        if eq <= 0:
            continue  # cannot ratio without equity
        sym, top_mv = top[account]
        out[account] = {
            "gross_ratio": g / eq,
            "concentration": top_mv / eq,
            "top_symbol": sym,
            "equity": eq,
        }
    return out


def _drawdown_metrics(con):
    """Latest max_drawdown (dollars) per (strategy, account)."""
    return {
        (s, a): float(dd)
        for s, a, dd in con.execute(_LATEST_DRAWDOWN).fetchall()
    }


def _severity(value, warn, breach):
    """'breach', 'warn', or None for a metric measured against ascending thresholds."""
    if value >= breach:
        return "breach"
    if value >= warn:
        return "warn"
    return None


def _derive_alerts(account_metrics, drawdown, now=None):
    """Build alert dicts (no DB writes). Account-level alerts use strategy_name=''."""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    alerts = []

    def add(account, strategy, alert_type, value, warn, breach, detail):
        sev = _severity(value, warn, breach)
        if sev is None:
            return
        alerts.append({
            "alert_date": today,
            "account_name": account,
            "strategy_name": strategy,
            "alert_type": alert_type,
            "severity": sev,
            "metric_value": value,
            "threshold": breach if sev == "breach" else warn,
            "detail": detail,
            "computed_at": now,
        })

    for account, m in account_metrics.items():
        add(account, "", "gross_exposure", m["gross_ratio"],
            GROSS_EXPOSURE_WARN, GROSS_EXPOSURE_BREACH,
            f"gross exposure {m['gross_ratio']:.2f}x equity")
        add(account, "", "concentration", m["concentration"],
            CONCENTRATION_WARN, CONCENTRATION_BREACH,
            f"{m['top_symbol']} is {m['concentration'] * 100:.1f}% of equity")

    # Drawdown is per-strategy; ratio it against the strategy's account equity.
    for (strategy, account), dd in drawdown.items():
        m = account_metrics.get(account)
        if not m or m["equity"] <= 0:
            continue
        ratio = dd / m["equity"]
        add(account, strategy, "drawdown", ratio,
            DRAWDOWN_WARN, DRAWDOWN_BREACH,
            f"max drawdown ${dd:,.0f} = {ratio * 100:.1f}% of equity")

    return alerts


def run(con):
    con.execute(DDL)
    now = datetime.now(timezone.utc)
    alerts = _derive_alerts(_account_metrics(con), _drawdown_metrics(con), now=now)
    for a in alerts:
        con.execute(_UPSERT_ALERT, [
            a["alert_date"], a["account_name"], a["strategy_name"], a["alert_type"],
            a["severity"], a["metric_value"], a["threshold"], a["detail"], a["computed_at"],
        ])
    # Remove today's alerts from earlier runs that did not fire this run (a breach cleared),
    # so the Dive shows only currently-breaching limits. Runs even when alerts is empty.
    con.execute(
        "DELETE FROM trading.main.risk_alerts WHERE alert_date = ? AND computed_at < ?",
        [now.date(), now],
    )
    return len(alerts)


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    n = run(con)
    print(f"risk_alerts written: {n}")


if __name__ == "__main__":
    main()
