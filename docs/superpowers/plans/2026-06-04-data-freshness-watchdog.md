# Data-Freshness Watchdog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a MotherDuck Flight that watches the *data* (not the processes `watchdog.py` watches) — flagging strategies that didn't write a snapshot today, orders stuck unfilled, and stale position snapshots — into a new `trading.main.health_alerts` table, surfaced by a `data-health` Dive, all deployable from the MotherDuck CLI.

**Architecture:** A pure-SQL+Python Flight (`flights/health/data_health.py`) modeled on `flights/aggregation/daily_pnl.py`: `DDL` constant, pure check functions taking a DuckDB connection, a `run(con)` orchestrator, and a thin `main()`. The expected set of `(strategy, account)` pairs comes from `core.accounts._ACCOUNT_STRATEGIES` (the same source the exec Flights use), so the watchdog and the live system can never disagree on what *should* report. Alerts upsert idempotently on `(check_date, account_name, strategy_name, check_type)`.

**Tech Stack:** Python 3, `duckdb` (`1.5.2`, `md:`), `core.accounts`, pytest (in-memory DuckDB), React + `@motherduck/react-sql-query`, MotherDuck CLI (preview).

---

## CLI note

Same mechanics as the risk-monitor plan: table DDL/queries run via `duckdb "md:" -c "..."`; the Dive deploys via `MD_CREATE_DIVE` / `MD_UPDATE_DIVE_CONTENT`; the Flight is created with your preview CLI's flight-create verb (entrypoint `flights/health/data_health.py:main`, requirements `flights/health/requirements.txt`, cron `0 21 * * 1-5` UTC — ~5pm ET, after the trading day — and the exec `access_token_name`).

## File Structure

- Create: `flights/health/__init__.py` (empty).
- Create: `flights/health/data_health.py` — DDL, check functions, `run(con)`, `main()`.
- Create: `flights/health/requirements.txt` — Flight deps (mirror `flights/exec/requirements.txt`, no `alpaca-py`).
- Create: `dives/data-health.tsx` — read-only Dive listing today's health alerts.
- Create: `tests/flights/health/__init__.py` (empty).
- Create: `tests/flights/health/test_data_health.py` — unit tests on injected in-memory DuckDB.

---

## Task 1: Schema DDL + table creation

**Files:**
- Create: `flights/health/__init__.py` (empty), `flights/health/data_health.py`
- Create: `tests/flights/health/__init__.py` (empty), `tests/flights/health/test_data_health.py`

(Note: `tests/flights/__init__.py` already exists if the risk-monitor plan ran; create it too if absent.)

- [ ] **Step 1: Create package markers**

Create empty files `flights/health/__init__.py` and `tests/flights/health/__init__.py` (and `tests/flights/__init__.py` if missing).

- [ ] **Step 2: Write the failing test**

`tests/flights/health/test_data_health.py`:

```python
"""data-health Flight unit tests on an in-memory DuckDB connection."""
import datetime as dt

import duckdb

from core.motherduck_logger import MotherDuckLogger
from flights.health import data_health


def _base_con():
    con = duckdb.connect()
    MotherDuckLogger(con=con)
    return con


def test_run_creates_health_alerts_table():
    con = _base_con()
    data_health.run(con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "health_alerts" in {r[0] for r in tables}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/flights/health/test_data_health.py::test_run_creates_health_alerts_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flights.health.data_health'`.

- [ ] **Step 4: Write minimal implementation**

`flights/health/data_health.py`:

```python
"""data-health Flight.

Watches the trading data for freshness/integrity problems and writes them to
trading.main.health_alerts. Pure MotherDuck SQL + Python; only MOTHERDUCK_TOKEN is needed.

Three checks:
  - missing_snapshot : an expected (strategy, account) wrote no portfolio_snapshot today
  - unfilled_order   : a trade is still status='submitted' hours after submission
  - stale_positions  : an account's most recent positions snapshot is older than the threshold

The expected (strategy, account) universe comes from core.accounts so it always matches what the
exec Flights actually run.
"""
import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS trading.main.health_alerts (
    check_date    DATE NOT NULL,
    account_name  VARCHAR NOT NULL,
    strategy_name VARCHAR NOT NULL,
    check_type    VARCHAR NOT NULL,
    detail        VARCHAR,
    computed_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (check_date, account_name, strategy_name, check_type)
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

Run: `pytest tests/flights/health/test_data_health.py::test_run_creates_health_alerts_table -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add flights/health/__init__.py flights/health/data_health.py tests/flights/__init__.py tests/flights/health/__init__.py tests/flights/health/test_data_health.py
git commit -m "feat(health): data_health Flight skeleton + health_alerts DDL"
```

---

## Task 2: Missing-snapshot check

**Files:**
- Modify: `flights/health/data_health.py`
- Test: `tests/flights/health/test_data_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/health/test_data_health.py`:

```python
def _insert_equity(con, account, strategy, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.portfolio_snapshots
            (snapshot_at, strategy_name, account_name, equity, cash, buying_power)
        VALUES (?, ?, ?, 100000, 0, 0)
        """,
        [snapshot_at, strategy, account],
    )


def test_missing_snapshots_uses_accounts_map():
    con = _base_con()
    now = dt.datetime.now(dt.timezone.utc)
    # Only stat_arb reported today; its account-mates and other accounts did not.
    _insert_equity(con, "stat_arb", "stat_arb", now)
    missing = data_health._missing_snapshots(con)
    pairs = {(m["strategy_name"], m["account_name"]) for m in missing}
    assert ("stat_arb", "stat_arb") not in pairs        # it reported
    assert ("stat_arb_v2", "stat_arb") in pairs          # account-mate missing
    assert ("trend_following", "macro_vol") in pairs      # other account missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/health/test_data_health.py::test_missing_snapshots_uses_accounts_map -v`
Expected: FAIL with `AttributeError: ... no attribute '_missing_snapshots'`.

- [ ] **Step 3: Write implementation**

Add to `flights/health/data_health.py` (add `from datetime import datetime, timezone` and `from core.accounts import _ACCOUNT_STRATEGIES` at top):

```python
# Today in US Eastern (market calendar), matching the daily_pnl Flight's convention.
_TODAY_ET = "(now() AT TIME ZONE 'America/New_York')::DATE"

_REPORTED_TODAY = f"""
SELECT DISTINCT strategy_name, account_name
FROM trading.main.portfolio_snapshots
WHERE (snapshot_at AT TIME ZONE 'America/New_York')::DATE = {_TODAY_ET}
"""


def _expected_pairs():
    """All (strategy, account) pairs that should report, from core.accounts."""
    return {
        (strategy, account)
        for account, strategies in _ACCOUNT_STRATEGIES.items()
        for strategy in strategies
    }


def _missing_snapshots(con):
    reported = {(s, a) for s, a in con.execute(_REPORTED_TODAY).fetchall()}
    now = datetime.now(timezone.utc)
    today = now.date()
    out = []
    for strategy, account in sorted(_expected_pairs() - reported):
        out.append({
            "check_date": today,
            "account_name": account,
            "strategy_name": strategy,
            "check_type": "missing_snapshot",
            "detail": "no portfolio_snapshot written today",
            "computed_at": now,
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/health/test_data_health.py::test_missing_snapshots_uses_accounts_map -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flights/health/data_health.py tests/flights/health/test_data_health.py
git commit -m "feat(health): missing-snapshot check from accounts map"
```

---

## Task 3: Unfilled-order check

**Files:**
- Modify: `flights/health/data_health.py`
- Test: `tests/flights/health/test_data_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/health/test_data_health.py`:

```python
def _insert_submitted_order(con, order_id, strategy, account, submitted_at):
    con.execute(
        """
        INSERT INTO trading.main.trades
            (order_id, strategy_name, account_name, symbol, side, qty, submitted_at, status)
        VALUES (?, ?, ?, 'AAPL', 'buy', 10, ?, 'submitted')
        """,
        [order_id, strategy, account, submitted_at],
    )


def test_unfilled_orders_flags_only_old_submitted():
    con = _base_con()
    now = dt.datetime.now(dt.timezone.utc)
    _insert_submitted_order(con, "old-1", "stat_arb", "stat_arb", now - dt.timedelta(hours=5))
    _insert_submitted_order(con, "fresh-1", "stat_arb", "stat_arb", now - dt.timedelta(minutes=10))
    alerts = data_health._unfilled_orders(con, max_age_hours=2)
    ids = {a["detail"] for a in alerts}
    assert any("old-1" in d for d in ids)
    assert not any("fresh-1" in d for d in ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/health/test_data_health.py::test_unfilled_orders_flags_only_old_submitted -v`
Expected: FAIL with `AttributeError: ... no attribute '_unfilled_orders'`.

- [ ] **Step 3: Write implementation**

Add to `flights/health/data_health.py`:

```python
_OLD_SUBMITTED = """
SELECT order_id, strategy_name, account_name, symbol, submitted_at
FROM trading.main.trades
WHERE status = 'submitted'
  AND submitted_at < now() - (? * INTERVAL 1 HOUR)
ORDER BY submitted_at
"""


def _unfilled_orders(con, max_age_hours=2):
    now = datetime.now(timezone.utc)
    today = now.date()
    rows = con.execute(_OLD_SUBMITTED, [max_age_hours]).fetchall()
    out = []
    for order_id, strategy, account, symbol, submitted_at in rows:
        out.append({
            "check_date": today,
            "account_name": account,
            "strategy_name": strategy,
            "check_type": "unfilled_order",
            "detail": f"order {order_id} ({symbol}) unfilled since {submitted_at}",
            "computed_at": now,
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/health/test_data_health.py::test_unfilled_orders_flags_only_old_submitted -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flights/health/data_health.py tests/flights/health/test_data_health.py
git commit -m "feat(health): unfilled-order check"
```

---

## Task 4: Stale-positions check

**Files:**
- Modify: `flights/health/data_health.py`
- Test: `tests/flights/health/test_data_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/health/test_data_health.py`:

```python
def _insert_position(con, account, strategy, snapshot_at):
    con.execute(
        """
        INSERT INTO trading.main.positions
            (snapshot_at, strategy_name, account_name, symbol, qty, avg_entry_price,
             current_price, unrealized_pnl)
        VALUES (?, ?, ?, 'AAPL', 10, 100, 100, 0)
        """,
        [snapshot_at, strategy, account],
    )


def test_stale_positions_flags_old_latest_snapshot():
    con = _base_con()
    now = dt.datetime.now(dt.timezone.utc)
    _insert_position(con, "stat_arb", "stat_arb", now - dt.timedelta(hours=4))   # stale account
    _insert_position(con, "macro_vol", "trend_following", now - dt.timedelta(minutes=20))  # fresh
    alerts = data_health._stale_positions(con, max_age_minutes=120)
    accounts = {a["account_name"] for a in alerts}
    assert "stat_arb" in accounts
    assert "macro_vol" not in accounts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/health/test_data_health.py::test_stale_positions_flags_old_latest_snapshot -v`
Expected: FAIL with `AttributeError: ... no attribute '_stale_positions'`.

- [ ] **Step 3: Write implementation**

Add to `flights/health/data_health.py`:

```python
# Most recent positions snapshot per account; flag if older than the threshold.
_LATEST_POSITION_AGE = """
SELECT account_name, max_snap,
       date_diff('minute', max_snap, now()) AS age_min
FROM (
    SELECT account_name, MAX(snapshot_at) AS max_snap
    FROM trading.main.positions
    GROUP BY account_name
)
WHERE date_diff('minute', max_snap, now()) > ?
"""


def _stale_positions(con, max_age_minutes=120):
    now = datetime.now(timezone.utc)
    today = now.date()
    rows = con.execute(_LATEST_POSITION_AGE, [max_age_minutes]).fetchall()
    out = []
    for account, max_snap, age_min in rows:
        out.append({
            "check_date": today,
            "account_name": account,
            "strategy_name": "",
            "check_type": "stale_positions",
            "detail": f"latest positions snapshot {int(age_min)} min old (>{max_age_minutes})",
            "computed_at": now,
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/health/test_data_health.py::test_stale_positions_flags_old_latest_snapshot -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flights/health/data_health.py tests/flights/health/test_data_health.py
git commit -m "feat(health): stale-positions check"
```

---

## Task 5: Wire run(con) — upsert + stale cleanup

**Files:**
- Modify: `flights/health/data_health.py`
- Test: `tests/flights/health/test_data_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/health/test_data_health.py`:

```python
def test_run_writes_and_is_idempotent():
    con = _base_con()
    # No snapshots at all -> every expected pair is a missing_snapshot alert.
    data_health.run(con)
    data_health.run(con)  # must not duplicate
    n = con.execute(
        "SELECT count(*) FROM trading.main.health_alerts WHERE check_type='missing_snapshot'"
    ).fetchone()[0]
    assert n == len(data_health._expected_pairs())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/health/test_data_health.py::test_run_writes_and_is_idempotent -v`
Expected: FAIL — `run` only creates the table, so count is 0.

- [ ] **Step 3: Write implementation**

Add the upsert constant and replace `run` in `flights/health/data_health.py`:

```python
_UPSERT_ALERT = """
INSERT INTO trading.main.health_alerts
    (check_date, account_name, strategy_name, check_type, detail, computed_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (check_date, account_name, strategy_name, check_type) DO UPDATE SET
    detail = EXCLUDED.detail,
    computed_at = EXCLUDED.computed_at
"""


def run(con):
    con.execute(DDL)
    alerts = (
        _missing_snapshots(con)
        + _unfilled_orders(con)
        + _stale_positions(con)
    )
    for a in alerts:
        con.execute(_UPSERT_ALERT, [
            a["check_date"], a["account_name"], a["strategy_name"],
            a["check_type"], a["detail"], a["computed_at"],
        ])
    # Drop today's rows from earlier runs that did not recur this run (issue resolved).
    if alerts:
        latest = max(a["computed_at"] for a in alerts)
        con.execute(
            "DELETE FROM trading.main.health_alerts WHERE check_date = ? AND computed_at < ?",
            [alerts[0]["check_date"], latest],
        )
    return len(alerts)
```

Note: `_unfilled_orders` and `_stale_positions` are called with their default thresholds (2h / 120min). To tune later, lift the defaults into a `flights/health/config.py` like the risk plan.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/health/test_data_health.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Add print to main()**

Replace `main()`:

```python
def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    n = run(con)
    print(f"health_alerts written: {n}")
```

- [ ] **Step 6: Commit**

```bash
git add flights/health/data_health.py tests/flights/health/test_data_health.py
git commit -m "feat(health): idempotent upsert + resolved-alert cleanup in run()"
```

---

## Task 6: Flight requirements

**Files:**
- Create: `flights/health/requirements.txt`

- [ ] **Step 1: Create requirements**

`flights/health/requirements.txt` — copy `flights/exec/requirements.txt`, drop the `alpaca-py` line, keep `duckdb==1.5.2` and the `git+https://...` repo line (needed so `flights.health.data_health` and `core.accounts` import).

- [ ] **Step 2: Commit**

```bash
git add flights/health/requirements.txt
git commit -m "feat(health): Flight requirements for data-health"
```

---

## Task 7: data-health Dive

**Files:**
- Create: `dives/data-health.tsx`

- [ ] **Step 1: Author the Dive**

`dives/data-health.tsx` (follows `dives/_conventions.tsx`):

```tsx
import { useSQLQuery } from "@motherduck/react-sql-query";

const N = (v: unknown): number => (v != null ? Number(v) : 0);

const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const RULE = "#e4e4e4";
const ROW_RULE = "#efefef";
const PNL_RED = "#bc1200";

const TYPE_LABEL: Record<string, string> = {
  missing_snapshot: "Missing snapshot",
  unfilled_order: "Unfilled order",
  stale_positions: "Stale positions",
};

export default function DataHealth() {
  const { data, isLoading, isError } = useSQLQuery(`
    SELECT
      check_type,
      account_name,
      strategy_name,
      detail,
      strftime(computed_at, '%Y-%m-%d %H:%M') AS computed_at
    FROM "trading"."main"."health_alerts"
    WHERE check_date = (now() AT TIME ZONE 'America/New_York')::DATE
    ORDER BY check_type, account_name, strategy_name
  `);

  const rows = Array.isArray(data) ? data : [];
  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>Data Health</h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Data-freshness & integrity alerts · today
          </p>
        </header>

        {isLoading ? (
          <p style={{ color: MUTED }}>Loading…</p>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading health alerts.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: "#2d7a00" }}>
            All clear — no data-health alerts today.
          </p>
        ) : (
          <table className="w-full text-sm" style={{ borderCollapse: "collapse", color: INK }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${RULE}` }}>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Check</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Account</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Detail</th>
                <th className="py-2 text-right text-xs font-semibold" style={{ color: MUTED }}>As of</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${ROW_RULE}` }}>
                  <td className="py-1.5 pr-4 font-medium" style={{ color: PNL_RED }}>
                    {TYPE_LABEL[String(r.check_type)] ?? String(r.check_type)}
                  </td>
                  <td className="py-1.5 pr-4">{String(r.account_name)}</td>
                  <td className="py-1.5 pr-4">{String(r.strategy_name) || "—"}</td>
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

Note: empty-state text intentionally differs from the other Dives — for a health board, "all clear" (green) is the meaningful empty state, not "no data yet."

- [ ] **Step 2: Commit**

```bash
git add dives/data-health.tsx
git commit -m "feat(health): data-health Dive"
```

---

## Task 8: Deploy + verify from the CLI

**Files:** none (operational).

- [ ] **Step 1: Run the suite**

Run: `pytest tests/flights/health/ -v`
Expected: all PASS.

- [ ] **Step 2: Smoke-test the DDL via CLI**

Run: `duckdb "md:" -c "$(python3 -c 'from flights.health.data_health import DDL; print(DDL)')"`
Expected: no error.

- [ ] **Step 3: Deploy the Dive via CLI**

Run: `duckdb "md:" -c "SELECT * FROM MD_CREATE_DIVE(title => 'data-health', content => readtext('dives/data-health.tsx'), description => 'Data-freshness & integrity alerts')"`
Record the dive id.

- [ ] **Step 4: Create + run the Flight via CLI**

Create the Flight (entrypoint `flights/health/data_health.py:main`, requirements `flights/health/requirements.txt`, cron `0 21 * * 1-5`, exec `access_token_name`), trigger one run, tail logs. Expected: `health_alerts written: <n>`.

- [ ] **Step 5: Verify**

Run: `duckdb "md:" -c "SELECT check_type, count(*) FROM trading.main.health_alerts WHERE check_date = (now() AT TIME ZONE 'America/New_York')::DATE GROUP BY check_type"`
Open the `data-health` Dive; confirm rows match.

---

## Self-Review

- **Spec coverage:** missing-snapshot (Task 2), unfilled-order (Task 3), stale-positions (Task 4), new `health_alerts` table (Task 1), Flight (Tasks 1/5/6), Dive (Task 7), CLI deploy (Task 8) — all covered. Expected-set sourced from `core.accounts` per the architecture.
- **Placeholders:** none; all code complete. CLI flight-create flags named-not-syntaxed (no SQL function for Flights).
- **Type consistency:** all three check functions return dicts with the same six keys (`check_date`, `account_name`, `strategy_name`, `check_type`, `detail`, `computed_at`), concatenated in `run` and fed to `_UPSERT_ALERT` in matching order. `_expected_pairs()` is used by both the check and the idempotency test.
- **Import note:** uses `core.accounts._ACCOUNT_STRATEGIES` (private) deliberately — it's the authoritative map; if a public accessor is later added to `core/accounts.py`, switch to it.
