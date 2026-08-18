# Backtest-vs-Live Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist backtest results to a new `trading.main.backtest_runs` table and add a `backtest-vs-live` Dive that compares each strategy's *backtested* Sharpe/return against its *live* performance (from `daily_pnl`), so out-of-sample drift is visible — all driven through the MotherDuck CLI.

**Architecture:** A `BacktestLogger` class (`core/backtest_logger.py`) mirrors `core/motherduck_logger.py` exactly: no import-time connection, idempotent `CREATE TABLE IF NOT EXISTS` on construction, accepts an injected connection for tests. It appends one row per backtest run (a *history*, intentionally not deduped). A thin script (`scripts/log_backtest.py`) runs the stat_arb backtest grid point and logs each seed's result. A read-only Dive joins the latest backtest per strategy to a live annualized Sharpe computed in SQL from `daily_pnl`.

**Tech Stack:** Python 3, `duckdb` (`md:`), `strategies.stat_arb.backtest` (`BacktestParams`, `run_backtest`), pytest (in-memory DuckDB), React + `@motherduck/react-sql-query`, MotherDuck CLI (preview).

---

## CLI note

`backtest_runs` is written locally (you run backtests on your machine) via `BacktestLogger` over `duckdb.connect("md:")` — the same connection style the rest of the repo uses; no Flight needed. The comparison **Dive** deploys via `MD_CREATE_DIVE` / `MD_UPDATE_DIVE_CONTENT` from the CLI. To exercise the CLI's *data-load* path as well, Task 6 includes an optional `COPY`-based load from a local parquet of backtest results.

## File Structure

- Create: `core/backtest_logger.py` — `BacktestLogger` (schema + `log_run`).
- Create: `scripts/log_backtest.py` — run stat_arb backtests and log them.
- Create: `dives/backtest-vs-live.tsx` — comparison Dive.
- Create: `tests/test_backtest_logger.py` — unit tests on injected in-memory DuckDB.

---

## Task 1: BacktestLogger schema

**Files:**
- Create: `core/backtest_logger.py`
- Test: `tests/test_backtest_logger.py`

- [ ] **Step 1: Write the failing test**

`tests/test_backtest_logger.py`:

```python
"""BacktestLogger unit tests on an in-memory DuckDB connection (mirrors test_motherduck_logger.py)."""
import duckdb

from core.backtest_logger import BacktestLogger


def _fake_result(total_return=0.12, annualized_sharpe=1.3,
                 max_drawdown=0.18, win_rate=0.55, num_trades=40):
    return type("R", (), {
        "total_return": total_return,
        "annualized_sharpe": annualized_sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "num_trades": num_trades,
    })()


def test_schema_creates_backtest_runs_table():
    con = duckdb.connect()
    BacktestLogger(con=con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "backtest_runs" in {r[0] for r in tables}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backtest_logger.py::test_schema_creates_backtest_runs_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.backtest_logger'`.

- [ ] **Step 3: Write minimal implementation**

`core/backtest_logger.py`:

```python
"""MotherDuck write layer for backtest results.

Mirrors core/motherduck_logger.py: no import-time connection, idempotent DDL on construction,
accepts an injected connection for tests. backtest_runs is an append-only history (one row per
run/seed) — the comparison Dive selects the latest row per strategy.
"""
import json
from datetime import datetime, timezone

import duckdb


class BacktestLogger:
    def __init__(self, token: str = None, con=None):
        if con is not None:
            self.con = con
        else:
            self.con = duckdb.connect("md:", config={"motherduck_token": token})
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            self.con.execute("CREATE DATABASE IF NOT EXISTS trading")
        except Exception:
            self.con.execute("ATTACH IF NOT EXISTS ':memory:' AS trading")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.backtest_runs (
                run_at            TIMESTAMPTZ NOT NULL,
                strategy_name     VARCHAR NOT NULL,
                params            VARCHAR,
                seed              INTEGER,
                total_return      DECIMAL(18,6),
                annualized_sharpe DECIMAL(18,6),
                max_drawdown      DECIMAL(18,6),
                win_rate          DECIMAL(18,6),
                num_trades        INTEGER,
                git_sha           VARCHAR
            )
        """)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_backtest_logger.py::test_schema_creates_backtest_runs_table -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/backtest_logger.py tests/test_backtest_logger.py
git commit -m "feat(backtest): BacktestLogger schema for backtest_runs"
```

---

## Task 2: log_run() method

**Files:**
- Modify: `core/backtest_logger.py`
- Test: `tests/test_backtest_logger.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_backtest_logger.py`:

```python
def test_log_run_writes_row_with_serialized_params():
    con = duckdb.connect()
    logger = BacktestLogger(con=con)
    logger.log_run(
        strategy_name="stat_arb",
        params={"entry_zscore": 2.5, "leverage": 1.0, "num_pairs": 5},
        seed=42,
        result=_fake_result(total_return=0.2, annualized_sharpe=1.5, num_trades=37),
        git_sha="abc123",
    )
    row = con.execute(
        "SELECT strategy_name, seed, total_return, annualized_sharpe, num_trades, params, git_sha "
        "FROM trading.main.backtest_runs"
    ).fetchone()
    assert row[0] == "stat_arb"
    assert row[1] == 42
    assert abs(float(row[2]) - 0.2) < 1e-6
    assert abs(float(row[3]) - 1.5) < 1e-6
    assert row[4] == 37
    assert '"entry_zscore": 2.5' in row[5]   # params serialized as JSON
    assert row[6] == "abc123"


def test_log_run_appends_history():
    con = duckdb.connect()
    logger = BacktestLogger(con=con)
    for seed in (42, 123):
        logger.log_run("stat_arb", {"leverage": 1.0}, seed, _fake_result(), git_sha=None)
    n = con.execute("SELECT count(*) FROM trading.main.backtest_runs").fetchone()[0]
    assert n == 2   # append-only, not deduped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backtest_logger.py -k log_run -v`
Expected: FAIL with `AttributeError: 'BacktestLogger' object has no attribute 'log_run'`.

- [ ] **Step 3: Write implementation**

Add the method to `BacktestLogger`:

```python
    def log_run(self, strategy_name: str, params: dict, seed: int, result, git_sha: str = None):
        """Append one backtest run. `params` is any JSON-serializable dict; `result` exposes
        total_return / annualized_sharpe / max_drawdown / win_rate / num_trades attributes."""
        self.con.execute(
            """
            INSERT INTO trading.main.backtest_runs
                (run_at, strategy_name, params, seed, total_return, annualized_sharpe,
                 max_drawdown, win_rate, num_trades, git_sha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                datetime.now(timezone.utc),
                strategy_name,
                json.dumps(params, sort_keys=True),
                int(seed),
                float(result.total_return),
                float(result.annualized_sharpe),
                float(result.max_drawdown),
                float(result.win_rate),
                int(result.num_trades),
                git_sha,
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_backtest_logger.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add core/backtest_logger.py tests/test_backtest_logger.py
git commit -m "feat(backtest): BacktestLogger.log_run appends run history"
```

---

## Task 3: log_backtest.py script

**Files:**
- Create: `scripts/log_backtest.py`

- [ ] **Step 1: Inspect the backtest API**

Run: `python3 -c "from strategies.stat_arb.backtest import BacktestParams, run_backtest; import dataclasses; print([f.name for f in dataclasses.fields(BacktestParams)])"`
Expected: prints the param field names (e.g. `entry_zscore`, `exit_zscore`, ...). Confirms `dataclasses.asdict` works for serialization.

- [ ] **Step 2: Write the script**

`scripts/log_backtest.py`:

```python
#!/usr/bin/env python3
"""Run the stat_arb backtest across seeds and log each result to trading.main.backtest_runs.

Requires MOTHERDUCK_TOKEN. Captures the current git SHA so each row is traceable to the code
that produced it. Run: python scripts/log_backtest.py
"""
import dataclasses
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest_logger import BacktestLogger
from strategies.stat_arb.backtest import BacktestParams, run_backtest

SEEDS = [42, 123, 777, 999, 1337]


def _git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return None


def main():
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        print("MOTHERDUCK_TOKEN not set — cannot log backtest results", file=sys.stderr)
        sys.exit(1)

    params = BacktestParams(
        entry_zscore=2.5, exit_zscore=0.0, stoploss_zscore=4.0,
        max_holding_days=120, leverage=1.0, rolling_window=60, num_pairs=10,
    )
    logger = BacktestLogger(token=token)
    sha = _git_sha()
    for seed in SEEDS:
        result = run_backtest(params, seed=seed)
        logger.log_run(
            strategy_name="stat_arb",
            params=dataclasses.asdict(params),
            seed=seed,
            result=result,
            git_sha=sha,
        )
        print(f"logged stat_arb seed={seed} sharpe={result.annualized_sharpe:.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify it imports cleanly (no token needed to import)**

Run: `python3 -c "import scripts.log_backtest"`
Expected: no error (importing must not connect — `BacktestLogger` is only instantiated inside `main`).

- [ ] **Step 4: Commit**

```bash
git add scripts/log_backtest.py
git commit -m "feat(backtest): script to run + log stat_arb backtests to MotherDuck"
```

---

## Task 4: backtest-vs-live comparison Dive

**Files:**
- Create: `dives/backtest-vs-live.tsx`

- [ ] **Step 1: Author the Dive**

`dives/backtest-vs-live.tsx` (follows `dives/_conventions.tsx`). Live annualized Sharpe is computed from `daily_pnl.realized_pnl` (`AVG/STDDEV * sqrt(252)`), guarded for variance/count:

```tsx
import { useSQLQuery } from "@motherduck/react-sql-query";

const N = (v: unknown): number => (v != null ? Number(v) : 0);

const INK = "#231f20";
const MUTED = "#6a6a6a";
const BG = "#f8f8f8";
const RULE = "#e4e4e4";
const ROW_RULE = "#efefef";
const PNL_GREEN = "#2d7a00";
const PNL_RED = "#bc1200";

export default function BacktestVsLive() {
  // latest backtest per strategy (avg across seeds of the most recent run_at), joined to a
  // live annualized Sharpe from daily_pnl. drift = live_sharpe - backtest_sharpe.
  const { data, isLoading, isError } = useSQLQuery(`
    WITH latest_bt AS (
      SELECT strategy_name, MAX(run_at) AS run_at
      FROM "trading"."main"."backtest_runs"
      GROUP BY strategy_name
    ),
    bt AS (
      SELECT b.strategy_name,
             AVG(b.annualized_sharpe) AS backtest_sharpe,
             AVG(b.total_return)      AS backtest_return
      FROM "trading"."main"."backtest_runs" b
      JOIN latest_bt l USING (strategy_name)
      WHERE b.run_at = l.run_at
      GROUP BY b.strategy_name
    ),
    live AS (
      SELECT strategy_name,
             CASE WHEN COUNT(*) >= 2 AND STDDEV_SAMP(realized_pnl) > 0
                  THEN (AVG(realized_pnl) / STDDEV_SAMP(realized_pnl)) * sqrt(252)
             END AS live_sharpe,
             SUM(realized_pnl) AS live_total_pnl
      FROM "trading"."main"."daily_pnl"
      GROUP BY strategy_name
    )
    SELECT
      bt.strategy_name,
      ROUND(bt.backtest_sharpe, 3) AS backtest_sharpe,
      ROUND(live.live_sharpe, 3)   AS live_sharpe,
      ROUND(live.live_sharpe - bt.backtest_sharpe, 3) AS drift,
      ROUND(100.0 * bt.backtest_return, 1) AS backtest_return_pct,
      ROUND(live.live_total_pnl, 2) AS live_total_pnl
    FROM bt
    LEFT JOIN live USING (strategy_name)
    ORDER BY bt.strategy_name
  `);

  const rows = Array.isArray(data) ? data : [];
  const fmt = (v: unknown, d: number) => (v == null ? "—" : N(v).toFixed(d));
  const usd = (v: unknown) =>
    v == null ? "—" : N(v).toLocaleString("en-US", { style: "currency", currency: "USD" });
  const numCell = { fontVariantNumeric: "tabular-nums" } as const;

  return (
    <div className="p-6" style={{ background: BG, color: INK }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <header className="mb-6">
          <h1 className="text-xl font-semibold" style={{ color: INK }}>Backtest vs Live</h1>
          <p className="text-sm" style={{ color: MUTED }}>
            Latest backtest Sharpe vs live annualized Sharpe · drift = live − backtest
          </p>
        </header>

        {isLoading ? (
          <p style={{ color: MUTED }}>Loading…</p>
        ) : isError ? (
          <p style={{ color: PNL_RED }}>Error loading comparison.</p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center" style={{ color: MUTED }}>
            No data yet — run scripts/log_backtest.py to populate.
          </p>
        ) : (
          <table className="w-full text-sm" style={{ borderCollapse: "collapse", color: INK }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${RULE}` }}>
                <th className="py-2 pr-4 text-left text-xs font-semibold" style={{ color: MUTED }}>Strategy</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Backtest Sharpe</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Live Sharpe</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Drift</th>
                <th className="py-2 pr-4 text-right text-xs font-semibold" style={{ color: MUTED }}>Backtest Return</th>
                <th className="py-2 text-right text-xs font-semibold" style={{ color: MUTED }}>Live P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${ROW_RULE}` }}>
                  <td className="py-1.5 pr-4 font-medium">{String(r.strategy_name)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{fmt(r.backtest_sharpe, 3)}</td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>{fmt(r.live_sharpe, 3)}</td>
                  <td className="py-1.5 pr-4 text-right" style={{ ...numCell, color: r.drift == null ? MUTED : N(r.drift) >= 0 ? PNL_GREEN : PNL_RED }}>
                    {fmt(r.drift, 3)}
                  </td>
                  <td className="py-1.5 pr-4 text-right" style={numCell}>
                    {r.backtest_return_pct == null ? "—" : `${N(r.backtest_return_pct).toFixed(1)}%`}
                  </td>
                  <td className="py-1.5 text-right" style={{ ...numCell, color: N(r.live_total_pnl) >= 0 ? PNL_GREEN : PNL_RED }}>
                    {usd(r.live_total_pnl)}
                  </td>
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

Note: live Sharpe annualized from *daily realized P&L* is directly comparable to the backtest's `annualized_sharpe`; both are NULL-tolerant (rendered "—") until enough live history accrues.

- [ ] **Step 2: Commit**

```bash
git add dives/backtest-vs-live.tsx
git commit -m "feat(backtest): backtest-vs-live comparison Dive"
```

---

## Task 5: Deploy + verify from the CLI

**Files:** none (operational).

- [ ] **Step 1: Run the suite**

Run: `pytest tests/test_backtest_logger.py -v`
Expected: all PASS.

- [ ] **Step 2: Populate backtest_runs**

Run: `MOTHERDUCK_TOKEN=<token> python scripts/log_backtest.py`
Expected: 5 `logged stat_arb seed=...` lines.

- [ ] **Step 3: Verify the table via CLI**

Run: `duckdb "md:" -c "SELECT strategy_name, seed, ROUND(annualized_sharpe,2) sharpe, git_sha FROM trading.main.backtest_runs ORDER BY run_at DESC LIMIT 5"`
Expected: 5 rows.

- [ ] **Step 4: Deploy the Dive via CLI**

Run: `duckdb "md:" -c "SELECT * FROM MD_CREATE_DIVE(title => 'backtest-vs-live', content => readtext('dives/backtest-vs-live.tsx'), description => 'Backtest vs live Sharpe drift')"`
Open the Dive; confirm `stat_arb` shows a backtest Sharpe (live Sharpe "—" until live history exists).

---

## Task 6 (optional): exercise the CLI data-load path

**Files:** none (operational).

- [ ] **Step 1: Dump backtest rows to local parquet via CLI**

Run: `duckdb "md:" -c "COPY (SELECT * FROM trading.main.backtest_runs) TO 'backtest_runs.parquet' (FORMAT parquet)"`

- [ ] **Step 2: Round-trip load from parquet via CLI**

Run: `duckdb "md:" -c "INSERT INTO trading.main.backtest_runs SELECT * FROM read_parquet('backtest_runs.parquet') LIMIT 0"`
Expected: confirms the CLI can read local parquet and write to MotherDuck (the `LIMIT 0` makes it a no-op schema check; drop the `LIMIT 0` to actually load external backtest exports). Delete the temp file when done: `rm backtest_runs.parquet`.

---

## Self-Review

- **Spec coverage:** new `backtest_runs` table (Task 1), result logging (Task 2), populate script (Task 3), comparison Dive (Task 4), CLI deploy/verify (Task 5), CLI data-load test (Task 6) — all covered.
- **Placeholders:** none; all code complete. CLI verbs use real SQL (`MD_CREATE_DIVE`, `COPY`, `read_parquet`).
- **Type consistency:** `log_run(strategy_name, params, seed, result, git_sha)` signature matches all call sites (test + script). `result` attribute names (`total_return`, `annualized_sharpe`, `max_drawdown`, `win_rate`, `num_trades`) match the real `BacktestResult` used in `scripts/run_backtest.py`. Dive column aliases (`backtest_sharpe`, `live_sharpe`, `drift`, `backtest_return_pct`, `live_total_pnl`) match their `r.<field>` reads.
- **Known v1 scope (explicit):** only `stat_arb` is wired in the script; other strategies have their own `run_backtest_*.py` and can be added by extending `SEEDS`/`params` per strategy. The Dive already supports any strategy present in `backtest_runs`.
