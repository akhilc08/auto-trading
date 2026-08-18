# Benchmark & Alpha/Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load SPY daily bars into a new `trading.main.benchmark_prices` table via a MotherDuck Flight (reusing the existing Alpaca secret), and add an `alpha-beta` Dive that computes each strategy's alpha and beta versus SPY directly in SQL (`regr_slope`/`regr_intercept`) — exercising the CLI's secret, data-load, Flight, and Dive surfaces.

**Architecture:** A Flight (`flights/benchmark/load_benchmark.py`) reuses `_read_alpaca_secret` and `_build_client` from `flights/exec/_runner.py` to fetch SPY daily bars (`AlpacaClient.get_historical_bars`, returning `{symbol: [Bar,...]}`), then upserts `(date, symbol, close)` into `benchmark_prices` idempotently. The bar→row upsert is a pure function unit-tested on in-memory DuckDB; the live Alpaca fetch (like the exec runner) is not unit-tested. The `alpha-beta` Dive derives daily strategy returns (`daily_pnl.realized_pnl / that-day equity`) and SPY daily returns, then regresses one on the other per strategy.

**Tech Stack:** Python 3, `duckdb` (`1.5.2`, `md:`), `alpaca-py`, reused helpers from `flights.exec._runner`, pytest (in-memory DuckDB), React + `@motherduck/react-sql-query`, MotherDuck CLI (preview).

---

## CLI note — `@motherduck/cli` from the `motherduck-cli-v1` branch

Verified by building and running it. **Use the `motherduck-cli-v1` branch, not `miguel/motherduck-cli`** — the latter crashes at startup on every command (its `dive` group eagerly imports the vanilla-extract preview, which throws when bundled). The v1 build runs cleanly. Invocation in these steps is `motherduck <...>` (assumes the v1 CLI on PATH / aliased to `bun <worktree>/cli-dist/motherduck.js`). Auth: `motherduck login` (OAuth device flow) or set `MOTHERDUCK_TOKEN`.

v1 command surface: `login · logout · status · query · dive (validate|publish|list|pull|watch) · flight (publish|run|runs|logs|list) · databases · shares · snapshots`. Note there is **no `secrets` command** in v1 (miguel's branch had one) — verify the Alpaca secret via `query` on `duckdb_secrets()` instead.

- **Table DDL + verification queries:** `motherduck query "<sql>"` — `--format table|json|csv|ndjson`, `--file <path>`, `--timeout <s>`. This is the `duckdb "md:" -c` replacement.
- **Secret check (no `secrets` cmd):** `motherduck query "SELECT name, type FROM duckdb_secrets() WHERE name = 'alpaca_stat_arb'"` — confirms the `http` secret exists (it was created out-of-band for the exec Flights).
- **SPY loader as a real Flight (CLI-native in v1):** `motherduck flight publish flights/benchmark/load_benchmark.py` with `--name benchmark-load --requirements flights/benchmark/requirements.txt --secret alpaca_stat_arb --access-token-name <service-account-token-label> --schedule "30 22 * * 1-5"`. Add `--run` to trigger immediately, or `motherduck flight run benchmark-load`. Inspect with `motherduck flight runs benchmark-load` and `motherduck flight logs benchmark-load <run_number>`. The Flight executes the file as `__main__` (our `if __name__ == "__main__": main()`), and `--secret alpaca_stat_arb` makes the Alpaca secret readable inside the run — exactly what `main()` expects.
- **Dive:** `motherduck dive validate dives/alpha-beta.tsx` (local transpile/export/import check — warns if `N()` is missing; verified PASS on existing repo Dives) → `motherduck dive publish dives/alpha-beta.tsx --title "alpha-beta"`. Publish creates via `MD_CREATE_DIVE` and writes a `dives/.dive-meta.json` sidecar holding the dive id, so later `publish` calls UPDATE the same dive (drop `--title`). `motherduck dive watch dives/alpha-beta.tsx` gives a hot-reload preview.
- **`trading` DB access from the Dive:** `dive publish` does not attach databases — that's the Dive content's job. Per `dives/_conventions.tsx`, the publisher owns `trading` so it's auto-available; if a published Dive errors resolving `"trading"`, add the one-line `export const REQUIRED_DATABASES = [{ type: "database", path: "trading", alias: "trading" }];` to `alpha-beta.tsx` and re-publish.

## File Structure

- Create: `flights/benchmark/__init__.py` (empty).
- Create: `flights/benchmark/load_benchmark.py` — DDL, `_upsert_bars`, `run(con, client, ...)`, `main()`.
- Create: `flights/benchmark/requirements.txt` — Flight deps (copy `flights/exec/requirements.txt`; keeps `alpaca-py`).
- Create: `dives/alpha-beta.tsx` — alpha/beta-vs-SPY Dive.
- Create: `tests/flights/benchmark/__init__.py` (empty).
- Create: `tests/flights/benchmark/test_load_benchmark.py` — unit tests on injected in-memory DuckDB.

---

## Task 1: Schema DDL + table creation

**Files:**
- Create: `flights/benchmark/__init__.py` (empty), `flights/benchmark/load_benchmark.py`
- Create: `tests/flights/benchmark/__init__.py` (empty), `tests/flights/benchmark/test_load_benchmark.py`

(Create `tests/flights/__init__.py` too if it does not already exist from another plan.)

- [ ] **Step 1: Create package markers**

Create empty files `flights/benchmark/__init__.py` and `tests/flights/benchmark/__init__.py` (and `tests/flights/__init__.py` if missing).

- [ ] **Step 2: Write the failing test**

`tests/flights/benchmark/test_load_benchmark.py`:

```python
"""benchmark-load Flight unit tests on an in-memory DuckDB connection."""
import datetime as dt

import duckdb

from core.motherduck_logger import MotherDuckLogger
from flights.benchmark import load_benchmark


def _base_con():
    con = duckdb.connect()
    MotherDuckLogger(con=con)  # creates the trading database + base tables
    return con


def test_run_creates_benchmark_prices_table():
    con = _base_con()
    load_benchmark.ensure_schema(con)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_catalog = 'trading'"
    ).fetchall()
    assert "benchmark_prices" in {r[0] for r in tables}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py::test_run_creates_benchmark_prices_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flights.benchmark.load_benchmark'`.

- [ ] **Step 4: Write minimal implementation**

`flights/benchmark/load_benchmark.py`:

```python
"""benchmark-load Flight.

Fetches SPY (and any configured) daily bars from Alpaca and upserts them into
trading.main.benchmark_prices for alpha/beta analysis. Reuses the exec Flight's secret-reading
and client-building helpers; reads market data via the existing alpaca_stat_arb secret.
"""
import duckdb
from alpaca.data.timeframe import TimeFrame

from flights.exec._runner import _read_alpaca_secret, _build_client

BENCHMARK_SYMBOLS = ["SPY"]
LOOKBACK_TRADING_DAYS = 400
SECRET_NAME = "alpaca_stat_arb"

DDL = """
CREATE TABLE IF NOT EXISTS trading.main.benchmark_prices (
    date   DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    close  DECIMAL(18,4) NOT NULL,
    PRIMARY KEY (date, symbol)
)
"""


def ensure_schema(con):
    con.execute(DDL)


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    ensure_schema(con)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py::test_run_creates_benchmark_prices_table -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add flights/benchmark/__init__.py flights/benchmark/load_benchmark.py tests/flights/__init__.py tests/flights/benchmark/__init__.py tests/flights/benchmark/test_load_benchmark.py
git commit -m "feat(benchmark): load_benchmark Flight skeleton + benchmark_prices DDL"
```

---

## Task 2: Pure bar→row upsert

**Files:**
- Modify: `flights/benchmark/load_benchmark.py`
- Test: `tests/flights/benchmark/test_load_benchmark.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/benchmark/test_load_benchmark.py`:

```python
def _fake_bar(ts, close):
    return type("Bar", (), {"timestamp": ts, "close": close})()


def test_upsert_bars_inserts_and_dedupes():
    con = _base_con()
    load_benchmark.ensure_schema(con)
    bars = [
        _fake_bar(dt.datetime(2026, 6, 1, 4, 0, tzinfo=dt.timezone.utc), 500.0),
        _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 505.0),
    ]
    load_benchmark._upsert_bars(con, "SPY", bars)
    # re-run with a corrected close for 2026-06-02 -> updates, not duplicates
    load_benchmark._upsert_bars(con, "SPY", [
        _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 506.0),
    ])
    rows = con.execute(
        "SELECT date, close FROM trading.main.benchmark_prices WHERE symbol='SPY' ORDER BY date"
    ).fetchall()
    assert len(rows) == 2
    assert str(rows[0][0]) == "2026-06-01"
    assert abs(float(rows[1][1]) - 506.0) < 1e-6   # updated close
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py::test_upsert_bars_inserts_and_dedupes -v`
Expected: FAIL with `AttributeError: ... no attribute '_upsert_bars'`.

- [ ] **Step 3: Write implementation**

Add to `flights/benchmark/load_benchmark.py`:

```python
_UPSERT = """
INSERT INTO trading.main.benchmark_prices (date, symbol, close)
VALUES (?, ?, ?)
ON CONFLICT (date, symbol) DO UPDATE SET close = EXCLUDED.close
"""


def _upsert_bars(con, symbol, bars):
    """Upsert Alpaca bars (objects with .timestamp datetime and .close) for one symbol.
    Returns the number of bars written."""
    n = 0
    for bar in bars:
        con.execute(_UPSERT, [bar.timestamp.date(), symbol, float(bar.close)])
        n += 1
    return n
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add flights/benchmark/load_benchmark.py tests/flights/benchmark/test_load_benchmark.py
git commit -m "feat(benchmark): idempotent bar->row upsert"
```

---

## Task 3: run(con, client) orchestrator + live main()

**Files:**
- Modify: `flights/benchmark/load_benchmark.py`
- Test: `tests/flights/benchmark/test_load_benchmark.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/flights/benchmark/test_load_benchmark.py`:

```python
class _FakeClient:
    """Stand-in for AlpacaClient.get_historical_bars returning {symbol: [Bar,...]}."""
    def get_historical_bars(self, symbols, n_days, timeframe=None):
        return {
            s: [
                _fake_bar(dt.datetime(2026, 6, 1, 4, 0, tzinfo=dt.timezone.utc), 500.0),
                _fake_bar(dt.datetime(2026, 6, 2, 4, 0, tzinfo=dt.timezone.utc), 505.0),
            ]
            for s in symbols
        }


def test_run_loads_symbols_from_client():
    con = _base_con()
    written = load_benchmark.run(con, _FakeClient(), symbols=["SPY"], n_days=10)
    assert written == 2
    n = con.execute(
        "SELECT count(*) FROM trading.main.benchmark_prices WHERE symbol='SPY'"
    ).fetchone()[0]
    assert n == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py::test_run_loads_symbols_from_client -v`
Expected: FAIL with `AttributeError: ... no attribute 'run'`.

- [ ] **Step 3: Write implementation**

Add `run` and rewrite `main` in `flights/benchmark/load_benchmark.py`:

```python
def run(con, client, symbols=BENCHMARK_SYMBOLS, n_days=LOOKBACK_TRADING_DAYS):
    ensure_schema(con)
    data = client.get_historical_bars(symbols, n_days, timeframe=TimeFrame.Day)
    written = 0
    for symbol in symbols:
        written += _upsert_bars(con, symbol, data.get(symbol, []))
    return written


def main():
    con = duckdb.connect("md:")
    con.execute("CREATE DATABASE IF NOT EXISTS trading")
    api_key, secret_key = _read_alpaca_secret(con, SECRET_NAME)
    client = _build_client(api_key, secret_key)
    written = run(con, client)
    print(f"benchmark_prices rows written: {written}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flights/benchmark/test_load_benchmark.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add flights/benchmark/load_benchmark.py tests/flights/benchmark/test_load_benchmark.py
git commit -m "feat(benchmark): run() orchestrator + secret-backed main()"
```

---

## Task 4: Flight requirements

**Files:**
- Create: `flights/benchmark/requirements.txt`

- [ ] **Step 1: Create requirements**

`flights/benchmark/requirements.txt` — copy `flights/exec/requirements.txt` verbatim (this Flight DOES need `alpaca-py` for market data, plus `duckdb==1.5.2` and the `git+https://...` repo line so `flights.benchmark.load_benchmark` and the reused `flights.exec._runner` helpers import).

- [ ] **Step 2: Commit**

```bash
git add flights/benchmark/requirements.txt
git commit -m "feat(benchmark): Flight requirements for benchmark-load"
```

---

## Task 5: alpha-beta Dive

**Files:**
- Create: `dives/alpha-beta.tsx`

- [ ] **Step 1: Author the Dive**

`dives/alpha-beta.tsx` (follows `dives/_conventions.tsx`). Daily strategy return = `realized_pnl / that-day equity`; SPY daily return from `benchmark_prices`; `beta = regr_slope`, `alpha (annualized) = regr_intercept * 252`:

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
```

- [ ] **Step 2: Commit**

```bash
git add dives/alpha-beta.tsx
git commit -m "feat(benchmark): alpha-beta vs SPY Dive"
```

---

## Task 6: Deploy + verify with the `motherduck` CLI (v1 branch)

**Files:** none (operational). Assumes the v1 `motherduck` CLI available and `motherduck login` done (or `MOTHERDUCK_TOKEN` set).

- [ ] **Step 1: Run the suite**

Run: `pytest tests/flights/benchmark/ -v`
Expected: all PASS.

- [ ] **Step 2: Confirm the data-access secret exists (CLI)**

Run: `motherduck query "SELECT name, type FROM duckdb_secrets() WHERE name = 'alpaca_stat_arb'"`
Expected: one row, type `http`. If absent, it must be created out-of-band (v1 has no `secrets` command).

- [ ] **Step 3: Create the table (CLI)**

Run: `motherduck query "$(python3 -c 'from flights.benchmark.load_benchmark import DDL; print("CREATE DATABASE IF NOT EXISTS trading; " + DDL)')"`
Expected: no error; `trading.main.benchmark_prices` now exists.

- [ ] **Step 4: Publish + run the loader Flight (CLI)**

Run: `motherduck flight publish flights/benchmark/load_benchmark.py --name benchmark-load --requirements flights/benchmark/requirements.txt --secret alpaca_stat_arb --access-token-name <service-account-token-label> --schedule "30 22 * * 1-5" --run`
Then inspect: `motherduck flight runs benchmark-load` to get the latest run number, and `motherduck flight logs benchmark-load <run_number>`.
Expected log line: `benchmark_prices rows written: <n>` (a few hundred SPY daily bars). (`--access-token-name` is the service-account token label the exec Flights use; `--secret alpaca_stat_arb` makes the Alpaca keys readable in the run.)

- [ ] **Step 5: Verify the prices loaded (CLI)**

Run: `motherduck query "SELECT symbol, count(*) AS days, min(date) AS first, max(date) AS last FROM trading.main.benchmark_prices GROUP BY symbol"`
Expected: one `SPY` row spanning ~400 trading days.

- [ ] **Step 6: Validate + publish the Dive (CLI)**

Run: `motherduck dive validate dives/alpha-beta.tsx`
Expected: `Result: PASS` (the inline `N()` helper satisfies the numeric-safety check).
Then: `motherduck dive publish dives/alpha-beta.tsx --title "alpha-beta"`
Expected: `Published: <url>` and a new `dives/.dive-meta.json`. Open the URL; beta/alpha render once a strategy has ≥2 overlapping days of `daily_pnl` + matching equity snapshots, else the empty state shows. (Re-publish edits with `motherduck dive publish dives/alpha-beta.tsx` — no `--title`.)

---

## Self-Review

- **Spec coverage:** SPY loader Flight reusing the secret (Tasks 1–4 — exercises secret-verify + data-load + new table + a real CLI-deployed Flight via v1's `flight publish --secret`), alpha/beta computation in SQL (Task 5 Dive), CLI verify/publish (Task 6 — `query` on `duckdb_secrets()`, `flight publish/run/logs`, `dive validate`/`publish`) — all covered. With v1 the CLI drives every surface #8 needs: query, flight, dive.
- **Placeholders:** none; all code complete. CLI flight-create flags named-not-syntaxed (no SQL function for Flights); Dive uses real `MD_CREATE_DIVE`.
- **Type consistency:** `run(con, client, symbols, n_days)` matches its test call and `main()` call (defaults supplied). `_upsert_bars(con, symbol, bars)` signature matches both call sites. Reused `_read_alpaca_secret(con, secret_name)` / `_build_client(api_key, secret_key)` signatures match `flights/exec/_runner.py`. Dive aliases (`n_days`, `beta`, `alpha_annual`) match the `r.<field>` reads. `client.get_historical_bars(symbols, n_days, timeframe=...)` matches `core/alpaca_client.py`.
- **Known v1 approximations (explicit):** (1) strategy daily return uses account-level equity attributed per strategy (the `_runner.py` duplication) — consistent across strategies in an account but not true per-strategy capital; (2) `regr_*` needs overlapping (strategy-day, SPY-day) pairs, so alpha/beta stay "—" until live P&L history accrues. Both acceptable for a first cut.
