# Risk Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an intraday MotherDuck Flight that reads the latest positions/portfolio/drawdown data, detects risk-limit breaches (gross exposure, single-name concentration, strategy drawdown), writes them to a new `trading.main.risk_alerts` table, and surfaces them in a new `risk-alerts` Dive — all deployable from the MotherDuck CLI.

**Architecture:** A pure-SQL+Python Flight (`flights/risk/risk_monitor.py`) modeled exactly on `flights/aggregation/daily_pnl.py`: a `DDL` constant, pure compute functions that take a DuckDB connection, a `run(con)` orchestrator, and a thin `main()` that connects via `duckdb.connect("md:")`. Account-level exposure metrics dedupe the per-strategy-duplicated snapshot rows by taking the most recent row per `(account, symbol)`. Alerts are upserted idempotently keyed on `(alert_date, account_name, strategy_name, alert_type)` so re-running within a day refreshes rather than duplicates. A read-only Dive renders active alerts color-coded by severity.

**Tech Stack:** Python 3, `duckdb` (pinned `1.5.2`, MotherDuck `md:` connection), pytest (in-memory DuckDB), React + `@motherduck/react-sql-query` (Dive), MotherDuck CLI (preview) for deploy.

---

## CLI note

- **Table + queries:** any SQL the Flight runs also runs from the CLI: `duckdb "md:" -c "<sql>"`.
- **Dive:** deploy via the documented SQL functions, runnable from the CLI:
  `duckdb "md:" -c "SELECT * FROM MD_CREATE_DIVE(title => 'risk-alerts', content => '<contents of dives/risk-alerts.tsx>', description => 'Active risk-limit breaches')"`
  and `MD_UPDATE_DIVE_CONTENT(id => '<dive_id>', content => '<new contents>')` for updates. If your preview CLI exposes a higher-level `dive create`/`dive update` verb, use that instead — the `.tsx` file is the source of truth either way.
- **Flight:** no SQL function exists. Create the Flight with your CLI's flight-create verb using: entrypoint `flights/risk/risk_monitor.py:main`, requirements `flights/risk/requirements.txt`, an intraday cron (e.g. every 30 min during market hours: `*/30 13-20 * * 1-5` UTC), and `access_token_name` set to the same service-account token the exec Flights use. This mirrors the existing `create_flight` MCP calls.

## File Structure

- Create: `flights/risk/__init__.py` — package marker (empty).
- Create: `flights/risk/risk_monitor.py` — DDL, compute functions, `run(con)`, `main()`.
- Create: `flights/risk/config.py` — risk thresholds as plain constants (single source of truth).
- Create: `flights/risk/requirements.txt` — Flight deps (mirror `flights/exec/requirements.txt`).
- Create: `dives/risk-alerts.tsx` — read-only Dive listing active alerts.
- Create: `tests/flights/__init__.py` and `tests/flights/risk/__init__.py` — package markers (empty).
- Create: `tests/flights/risk/test_risk_monitor.py` — unit tests on injected in-memory DuckDB.

---

## Task 1: Risk thresholds config

**Files:**
- Create: `flights/risk/config.py`
- Create: `flights/risk/__init__.py` (empty)

- [ ] **Step 1: Create the package marker**

Create empty file `flights/risk/__init__.py` (no content).

- [ ] **Step 2: Write the thresholds**

`flights/risk/config.py`:

```python
"""Risk limits for the risk-monitor Flight. Ratios are fraction-of-equity (0.40 = 40%).

A 'warn' severity is emitted when the metric crosses the warn level; 'breach' when it
crosses the (higher) breach level. Tuned conservatively for paper trading; adjust per account
risk appetite. These are the single source of truth — the compute functions import from here.
"""

# Gross exposure = sum(|qty * current_price|) across an account's latest positions, / account equity.
GROSS_EXPOSURE_WARN = 1.5    # 150% of equity
GROSS_EXPOSURE_BREACH = 2.0  # 200% of equity

# Concentration = largest single position market value / account equity.
CONCENTRATION_WARN = 0.25    # 25%
CONCENTRATION_BREACH = 0.40  # 40%

# Drawdown = daily_pnl.max_drawdown (peak-to-trough cumulative realized P&L, dollars)
# expressed as a fraction of the account's latest equity.
DRAWDOWN_WARN = 0.05         # 5% of equity
DRAWDOWN_BREACH = 0.10       # 10% of equity
```

- [ ] **Step 3: Commit**

```bash
git add flights/risk/__init__.py flights/risk/config.py
git commit -m "feat(risk): add risk-monitor thresholds config"
```

---

## Task 2: Schema DDL + table creation

**Files:**
- Create: `flights/risk/risk_monitor.py`
- Test: `tests/flights/risk/test_risk_monitor.py`
- Create: `tests/flights/__init__.py`, `tests/flights/risk/__init__.py` (empty)

- [ ] **Step 1: Create test package markers**

Create empty files `tests/flights/__init__.py` and `tests/flights/risk/__init__.py`.

- [ ] **Step 2: Write the failing test**

`tests/flights/risk/test_risk_monitor.py`:

```python
"""risk-monitor Flight unit tests on an in-memory DuckDB connection.

Mirrors tests/test_motherduck_logger.py: a fresh duckdb.connect() with the base
trading tables created via MotherDuckLogger(con=...), then risk_monitor.run(con).
"""
import datetime as dt

import duckdb
import pytest

from core.motherduck_logger import MotherDuckLogger
from flights.risk import risk_monitor


def _base_con():
    """In-memory connection with the four base trading tables created."""
    con = duckdb.connect()
    MotherDuckLogger(con=con)  # creates trading.main.{trades,positions,portfolio_snapshots,daily_pnl}
    return con


def test_run_creates_risk_alerts_table():
    con = _base_con()
    risk_monitor.run(con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "risk_alerts" in {r[0] for r in tables}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_run_creates_risk_alerts_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flights.risk.risk_monitor'`.

- [ ] **Step 4: Write minimal implementation**

`flights/risk/risk_monitor.py`:

```python
"""risk-monitor Flight.

Reads the latest positions / portfolio / drawdown data and writes risk-limit breaches to
trading.main.risk_alerts. Pure MotherDuck SQL + Python; only MOTHERDUCK_TOKEN is needed
(no Alpaca credentials). Intended to run intraday during market hours.

Account-level metrics dedupe the per-strategy-duplicated snapshot rows: flights/exec/_runner.py
snapshots the same account-wide Alpaca positions once per strategy, so positions/portfolio rows
repeat across strategy_name. Taking the most recent row per (account, symbol) / per account
recovers the true account view.
"""
import duckdb

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


def run(con):
    con.execute(DDL)


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    run(con)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_run_creates_risk_alerts_table -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add flights/risk/risk_monitor.py tests/flights/__init__.py tests/flights/risk/__init__.py tests/flights/risk/test_risk_monitor.py
git commit -m "feat(risk): risk_monitor Flight skeleton + risk_alerts DDL"
```

---

## Task 3: Account exposure + concentration metrics

**Files:**
- Modify: `flights/risk/risk_monitor.py`
- Test: `tests/flights/risk/test_risk_monitor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/risk/test_risk_monitor.py`:

```python
def _insert_position(con, account, strategy, symbol, qty, price, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.positions
            (snapshot_at, strategy_name, account_name, symbol, qty, avg_entry_price,
             current_price, unrealized_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        [snapshot_at, strategy, account, symbol, qty, price, price],
    )


def _insert_equity(con, account, strategy, equity, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.portfolio_snapshots
            (snapshot_at, strategy_name, account_name, equity, cash, buying_power)
        VALUES (?, ?, ?, ?, 0, 0)
        """,
        [snapshot_at, strategy, account, equity],
    )


def test_account_metrics_dedupe_per_strategy_duplication():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    # Same account positions snapshotted under TWO strategies (the _runner.py duplication).
    for strat in ("stat_arb", "stat_arb_v2"):
        _insert_position(con, "stat_arb", strat, "AAPL", 100, 200.0, t)  # $20k
        _insert_position(con, "stat_arb", strat, "MSFT", 50, 100.0, t)   # $5k
        _insert_equity(con, "stat_arb", strat, 50000.0, t)
    metrics = risk_monitor._account_metrics(con)
    assert "stat_arb" in metrics
    m = metrics["stat_arb"]
    # gross = 20k + 5k = 25k (NOT doubled), equity 50k -> 0.5
    assert abs(m["gross_ratio"] - 0.5) < 1e-6
    # largest single position 20k / 50k = 0.4
    assert abs(m["concentration"] - 0.4) < 1e-6
    assert m["top_symbol"] == "AAPL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_account_metrics_dedupe_per_strategy_duplication -v`
Expected: FAIL with `AttributeError: module 'flights.risk.risk_monitor' has no attribute '_account_metrics'`.

- [ ] **Step 3: Write implementation**

Add to `flights/risk/risk_monitor.py` (above `run`):

```python
# Latest row per (account, symbol) across ALL strategies (dedupes the per-strategy duplication),
# and latest equity per account. Returns {account: {gross_ratio, concentration, top_symbol, equity}}.
_LATEST_POSITIONS = """
SELECT account_name, symbol, qty, current_price FROM (
    SELECT account_name, symbol, qty, current_price,
           ROW_NUMBER() OVER (PARTITION BY account_name, symbol ORDER BY snapshot_at DESC) AS rn
    FROM trading.main.positions
    WHERE current_price IS NOT NULL
) WHERE rn = 1
"""

_LATEST_EQUITY = """
SELECT account_name, equity FROM (
    SELECT account_name, equity,
           ROW_NUMBER() OVER (PARTITION BY account_name ORDER BY snapshot_at DESC) AS rn
    FROM trading.main.portfolio_snapshots
    WHERE equity IS NOT NULL
) WHERE rn = 1
"""


def _account_metrics(con):
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
            continue  # cannot ratio without equity; skip (a freshness check covers missing equity)
        sym, top_mv = top[account]
        out[account] = {
            "gross_ratio": g / eq,
            "concentration": top_mv / eq,
            "top_symbol": sym,
            "equity": eq,
        }
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_account_metrics_dedupe_per_strategy_duplication -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flights/risk/risk_monitor.py tests/flights/risk/test_risk_monitor.py
git commit -m "feat(risk): account exposure + concentration metrics (dedup-aware)"
```

---

## Task 4: Drawdown metric

**Files:**
- Modify: `flights/risk/risk_monitor.py`
- Test: `tests/flights/risk/test_risk_monitor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/risk/test_risk_monitor.py`:

```python
def _insert_daily_pnl(con, account, strategy, date, realized, max_dd):
    con.execute(
        """
        INSERT INTO trading.main.daily_pnl
            (date, strategy_name, account_name, realized_pnl, trade_count, win_count,
             sharpe_7d, max_drawdown)
        VALUES (?, ?, ?, ?, 1, 1, NULL, ?)
        """,
        [date, strategy, account, realized, max_dd],
    )


def test_drawdown_metrics_latest_per_strategy():
    con = _base_con()
    _insert_daily_pnl(con, "stat_arb", "stat_arb", dt.date(2026, 6, 2), 100.0, 1000.0)
    _insert_daily_pnl(con, "stat_arb", "stat_arb", dt.date(2026, 6, 3), -50.0, 6000.0)  # latest
    dd = risk_monitor._drawdown_metrics(con)
    assert abs(dd[("stat_arb", "stat_arb")] - 6000.0) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_drawdown_metrics_latest_per_strategy -v`
Expected: FAIL with `AttributeError: ... no attribute '_drawdown_metrics'`.

- [ ] **Step 3: Write implementation**

Add to `flights/risk/risk_monitor.py`:

```python
# Latest max_drawdown (dollars) per (strategy, account) from daily_pnl.
_LATEST_DRAWDOWN = """
SELECT strategy_name, account_name, max_drawdown FROM (
    SELECT strategy_name, account_name, max_drawdown,
           ROW_NUMBER() OVER (PARTITION BY strategy_name, account_name ORDER BY date DESC) AS rn
    FROM trading.main.daily_pnl
    WHERE max_drawdown IS NOT NULL
) WHERE rn = 1
"""


def _drawdown_metrics(con):
    return {
        (s, a): float(dd)
        for s, a, dd in con.execute(_LATEST_DRAWDOWN).fetchall()
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_drawdown_metrics_latest_per_strategy -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flights/risk/risk_monitor.py tests/flights/risk/test_risk_monitor.py
git commit -m "feat(risk): latest per-strategy drawdown metric"
```

---

## Task 5: Alert derivation (pure function)

**Files:**
- Modify: `flights/risk/risk_monitor.py`
- Test: `tests/flights/risk/test_risk_monitor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/risk/test_risk_monitor.py`:

```python
def test_derive_alerts_severities():
    account_metrics = {
        "stat_arb": {"gross_ratio": 2.1, "concentration": 0.30, "top_symbol": "AAPL", "equity": 50000.0},
    }
    drawdown = {("stat_arb", "stat_arb"): 6000.0}  # 6000/50000 = 0.12 -> breach (>0.10)
    alerts = risk_monitor._derive_alerts(account_metrics, drawdown)
    by_type = {(a["account_name"], a["strategy_name"], a["alert_type"]): a for a in alerts}

    # gross 2.1 -> breach; concentration 0.30 -> warn; drawdown 0.12 -> breach
    assert by_type[("stat_arb", "", "gross_exposure")]["severity"] == "breach"
    assert by_type[("stat_arb", "", "concentration")]["severity"] == "warn"
    assert by_type[("stat_arb", "stat_arb", "drawdown")]["severity"] == "breach"


def test_derive_alerts_below_warn_is_silent():
    account_metrics = {
        "stat_arb": {"gross_ratio": 1.0, "concentration": 0.10, "top_symbol": "AAPL", "equity": 50000.0},
    }
    drawdown = {("stat_arb", "stat_arb"): 1000.0}  # 0.02 -> below warn
    assert risk_monitor._derive_alerts(account_metrics, drawdown) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/risk/test_risk_monitor.py -k derive_alerts -v`
Expected: FAIL with `AttributeError: ... no attribute '_derive_alerts'`.

- [ ] **Step 3: Write implementation**

Add imports + function to `flights/risk/risk_monitor.py` (add `from flights.risk import config` and `from datetime import datetime, timezone` at top):

```python
def _severity(value, warn, breach):
    """Return 'breach', 'warn', or None for a metric measured against ascending thresholds."""
    if value >= breach:
        return "breach"
    if value >= warn:
        return "warn"
    return None


def _derive_alerts(account_metrics, drawdown):
    """Build alert dicts (no DB writes). Account-level alerts use strategy_name=''."""
    now = datetime.now(timezone.utc)
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
            config.GROSS_EXPOSURE_WARN, config.GROSS_EXPOSURE_BREACH,
            f"gross exposure {m['gross_ratio']:.2f}x equity")
        add(account, "", "concentration", m["concentration"],
            config.CONCENTRATION_WARN, config.CONCENTRATION_BREACH,
            f"{m['top_symbol']} is {m['concentration']*100:.1f}% of equity")

    # Drawdown is per-strategy; ratio it against the strategy's account equity.
    for (strategy, account), dd in drawdown.items():
        m = account_metrics.get(account)
        if not m or m["equity"] <= 0:
            continue
        ratio = dd / m["equity"]
        add(account, strategy, "drawdown", ratio,
            config.DRAWDOWN_WARN, config.DRAWDOWN_BREACH,
            f"max drawdown ${dd:,.0f} = {ratio*100:.1f}% of equity")

    return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/risk/test_risk_monitor.py -k derive_alerts -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add flights/risk/risk_monitor.py tests/flights/risk/test_risk_monitor.py
git commit -m "feat(risk): pure alert-derivation with warn/breach severities"
```

---

## Task 6: Wire run(con) to compute, upsert, and clear stale alerts

**Files:**
- Modify: `flights/risk/risk_monitor.py`
- Test: `tests/flights/risk/test_risk_monitor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/risk/test_risk_monitor.py`:

```python
def test_run_writes_alerts_and_is_idempotent():
    con = _base_con()
    t = dt.datetime(2026, 6, 4, 15, 0, tzinfo=dt.timezone.utc)
    for strat in ("stat_arb", "stat_arb_v2"):
        _insert_position(con, "stat_arb", strat, "AAPL", 100, 200.0, t)  # 20k
        _insert_position(con, "stat_arb", strat, "MSFT", 50, 100.0, t)   # 5k -> gross 25k
        _insert_equity(con, "stat_arb", strat, 10000.0, t)               # gross 2.5x -> breach
    risk_monitor.run(con)
    risk_monitor.run(con)  # second run must not duplicate
    rows = con.execute(
        "SELECT severity FROM trading.main.risk_alerts "
        "WHERE account_name='stat_arb' AND alert_type='gross_exposure'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "breach"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/risk/test_risk_monitor.py::test_run_writes_alerts_and_is_idempotent -v`
Expected: FAIL — `run` currently only creates the table, so 0 rows returned (`assert len(rows) == 1`).

- [ ] **Step 3: Write implementation**

Add the upsert constant and replace `run` in `flights/risk/risk_monitor.py`:

```python
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


def run(con):
    con.execute(DDL)
    alerts = _derive_alerts(_account_metrics(con), _drawdown_metrics(con))
    for a in alerts:
        con.execute(_UPSERT_ALERT, [
            a["alert_date"], a["account_name"], a["strategy_name"], a["alert_type"],
            a["severity"], a["metric_value"], a["threshold"], a["detail"], a["computed_at"],
        ])
    # Clear today's previously-written alerts that are no longer breaching (e.g. exposure dropped),
    # so the Dive shows only current breaches. Keyed on today's computed_at being older than this run.
    if alerts:
        latest = max(a["computed_at"] for a in alerts)
        con.execute(
            "DELETE FROM trading.main.risk_alerts WHERE alert_date = ? AND computed_at < ?",
            [alerts[0]["alert_date"], latest],
        )
    return len(alerts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/risk/test_risk_monitor.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Add the print to main() for Flight logs**

Replace `main()` in `flights/risk/risk_monitor.py`:

```python
def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    n = run(con)
    print(f"risk_alerts written: {n}")
```

- [ ] **Step 6: Commit**

```bash
git add flights/risk/risk_monitor.py tests/flights/risk/test_risk_monitor.py
git commit -m "feat(risk): idempotent upsert + stale-alert cleanup in run()"
```

---

## Task 7: Flight requirements file

**Files:**
- Create: `flights/risk/requirements.txt`

- [ ] **Step 1: Inspect the existing Flight requirements**

Run: `cat flights/exec/requirements.txt`
Note the `duckdb==1.5.2` pin and the `git+` repo install line.

- [ ] **Step 2: Create the risk Flight requirements**

`flights/risk/requirements.txt` — copy `flights/exec/requirements.txt` but drop the `alpaca-py` line (the risk Flight needs no Alpaca client). Keep `duckdb==1.5.2` and the `git+https://...` repo line so `flights.risk.risk_monitor` and `core.motherduck_logger` import.

- [ ] **Step 3: Commit**

```bash
git add flights/risk/requirements.txt
git commit -m "feat(risk): Flight requirements for risk-monitor"
```

---

## Task 8: risk-alerts Dive

**Files:**
- Create: `dives/risk-alerts.tsx`

- [ ] **Step 1: Author the Dive**

`dives/risk-alerts.tsx` — follow `dives/_conventions.tsx` exactly (inline `N()`, design tokens, fully-qualified quoted table name, empty-state text):

```tsx
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
          <p className="py-8 text-center" style={{ color: MUTED }}>
            No data yet — run a strategy to populate.
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
```

- [ ] **Step 2: Commit**

```bash
git add dives/risk-alerts.tsx
git commit -m "feat(risk): risk-alerts Dive"
```

---

## Task 9: Deploy + verify from the CLI

**Files:** none (operational).

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/flights/risk/ -v`
Expected: all PASS.

- [ ] **Step 2: Smoke-test the table DDL against MotherDuck via the CLI**

Run: `duckdb "md:" -c "$(python3 -c 'from flights.risk.risk_monitor import DDL; print(DDL)')"`
Expected: no error; `trading.main.risk_alerts` exists.

- [ ] **Step 3: Deploy the Dive via the CLI**

Run (substitute your preview CLI verb if it has one):
`duckdb "md:" -c "SELECT * FROM MD_CREATE_DIVE(title => 'risk-alerts', content => readtext('dives/risk-alerts.tsx'), description => 'Active risk-limit breaches')"`
Record the returned dive id.

- [ ] **Step 4: Create + run the Flight via the CLI**

Create the Flight (entrypoint `flights/risk/risk_monitor.py:main`, requirements `flights/risk/requirements.txt`, cron `*/30 13-20 * * 1-5`, `access_token_name` = exec service-account token), then trigger one run and tail its logs. Expected log line: `risk_alerts written: <n>`.

- [ ] **Step 5: Verify end-to-end**

Run: `duckdb "md:" -c "SELECT account_name, alert_type, severity, detail FROM trading.main.risk_alerts WHERE alert_date = (now() AT TIME ZONE 'America/New_York')::DATE ORDER BY severity"`
Open the `risk-alerts` Dive and confirm the same rows render with breach=red, warn=amber.

---

## Self-Review

- **Spec coverage:** gross exposure (Task 3/5), concentration (Task 3/5), drawdown (Task 4/5), new `risk_alerts` table (Task 2), Flight (Tasks 2/6/7), Dive (Task 8), CLI deploy (Task 9) — all covered.
- **Placeholders:** none; every code/SQL step is complete. CLI flight-create flags are intentionally named-not-syntaxed (no SQL function exists for Flights — preview CLI verb substituted).
- **Type consistency:** `_account_metrics` returns dicts with keys `gross_ratio`/`concentration`/`top_symbol`/`equity`, consumed identically in `_derive_alerts`. Alert dict keys match the `_UPSERT_ALERT` parameter order. `run(con)` returns the alert count used by `main()`.
- **Known v1 approximation (explicit):** drawdown is ratioed against the account's latest equity (strategy-level capital isn't tracked separately); noted in code comment and acceptable for a first cut.
