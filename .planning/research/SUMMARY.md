# Project Research Summary

**Project:** auto-trading — MotherDuck Cloud Deployment (v1.0 milestone)
**Domain:** Cloud trading analytics — scheduled execution + observability layer on top of Alpaca algo trading
**Researched:** 2026-06-02
**Confidence:** HIGH

## Executive Summary

This milestone adds a cloud observability and analytics layer to a working Alpaca-based algo trading system. The core work is: (1) write trade fills and position snapshots to MotherDuck from Python, (2) schedule the three-account strategy execution via GitHub Actions cron, and (3) create interactive Dives in the MotherDuck UI for equity curve, trade log, live positions, and strategy comparison. All four researchers independently confirmed that "MotherDuck Flights" does not exist as a product — the scheduled aggregation pipeline is implemented as a GitHub Actions cron job running Python that executes DuckDB SQL against MotherDuck. Dives ARE a real, well-documented product: interactive React visualizations that query live MotherDuck data and are created via the MotherDuck MCP tool or SQL function `MD_CREATE_DIVE`.

The recommended approach is additive and backward-compatible: add `core/motherduck_logger.py` as a new component, inject it into `OrderManager` (not `BaseStrategy`) via an optional parameter, and add three GitHub Actions workflow files (one per account, using matrix jobs for parallelism). The schema must include `strategy_name`, `account_name`, and `TIMESTAMPTZ` columns from day one — retrofitting these via `ALTER TABLE` after data exists creates NULL-backfill pain and corrupts historical comparisons. The aggregation job is a fourth GitHub Actions workflow writing `daily_pnl` rows post-market; Dives query this table directly.

The dominant operational risk is silent failure: MotherDuck writes failing while trades continue executing (personal token rotation, 60-day workflow disable, fill confirmation lag). Every mitigation points to the same pattern — use a service account token, monitor `portfolio_snapshots` for missing days, schedule aggregation at 6 PM ET not 4:30 PM ET, and make all MotherDuck inserts idempotent via `ON CONFLICT (order_id) DO NOTHING`.

---

## Key Findings

### Recommended Stack

The only new Python dependency is `duckdb>=1.1.0,<1.6.0`. The MotherDuck extension is bundled in the standard `duckdb` pip package — no separate install, no SQLAlchemy, no ORM. Connections use `duckdb.connect("md:trading", config={"motherduck_token": os.environ["MOTHERDUCK_TOKEN"]})`. Individual trade inserts use `execute()` or `executemany()` (row counts per run are single digits to tens, well below the 500-row executemany caution threshold). GitHub Actions versions: `actions/checkout@v4`, `actions/setup-python@v5`.

**Core technologies:**
- `duckdb>=1.1.0,<1.6.0`: Python-to-MotherDuck write layer — bundled MotherDuck extension, no extras needed; pin below 1.6 until MotherDuck confirms compatibility
- `GitHub Actions cron`: strategy execution scheduler — already the execution environment, no additional infrastructure
- `GitHub Actions cron (aggregation job)`: replacement for "MotherDuck Flights" — runs `core/aggregate.py` post-market to write `daily_pnl`; Dives query this table
- `MotherDuck Dives`: analytics visualizations — React components created once via MCP/`MD_CREATE_DIVE`, query live tables on each view; no Python dependencies required

### Expected Features

**Must have (table stakes):**
- `trades` table with `strategy_name`, `account_name`, `TIMESTAMPTZ` columns — every downstream feature depends on this schema being correct from row 1
- `positions` table with per-snapshot rows — required for live positions Dive
- `portfolio_snapshots` table — required for equity curve and drawdown Dives
- `MotherDuckLogger` injected into `OrderManager` — single integration point that captures all order events from all 13 strategies without modifying any strategy class
- Three GitHub Actions workflow files (stat_arb.yml, macro_vol.yml, trend_following.yml) — one per account, matrix jobs for parallel strategy execution
- Daily aggregation job writing `daily_pnl` — the "Flights" replacement; schedule at 6 PM ET to allow fill confirmation lag
- Trade log Dive and equity curve Dive — minimum viable observability

**Should have (differentiators):**
- Live positions Dive with unrealized P&L color-coding
- Strategy comparison Dive (Sharpe, drawdown, win rate across strategies)
- Per-account equity curve view (filter by `account_name` in Dive)
- Win rate by symbol (requires `pnl` column computed at fill time in Python, not SQL)
- Data freshness monitoring — alert if `portfolio_snapshots` has no rows for the last trading day

**Defer (v2+):**
- Strategy correlation heatmap — high SQL complexity, not needed for initial observability
- Drawdown recovery chart — multi-step window function, low priority
- Real-time streaming — Alpaca WebSocket cannot flow through MotherDuck; adds infrastructure
- Custom dashboard server (Grafana, Metabase) — Dives are the built-in solution; no additional infra

### Architecture Approach

The integration is additive: new file `core/motherduck_logger.py` plus optional parameter injection into `OrderManager.__init__`. No strategy files change. The logger holds a single `duckdb.connect()` for the lifetime of one runner.py execution (one GitHub Actions job). Position and portfolio snapshots are called from `runner.py` after `run_cron()` returns. The three account workflows use matrix jobs (one matrix value per strategy per account), keeping workflow files at 3 instead of 13 and making secret management per-account. The `MOTHERDUCK_TOKEN` secret is shared across all three workflows; Alpaca keys are per-account.

**Major components:**
1. `core/motherduck_logger.py` (NEW) — DuckDB connection lifecycle, schema creation via `CREATE TABLE IF NOT EXISTS`, `log_order()`, `snapshot_positions()`, `snapshot_portfolio()`
2. `core/order_manager.py` (MODIFIED) — accepts optional `md_logger=None`; calls `md_logger.log_order()` after each order submission in all 4 order methods; backward-compatible default
3. `runner.py` (MODIFIED) — constructs `MotherDuckLogger`, passes to `OrderManager`, calls snapshot methods after `run_cron`; guarded by env var check so local runs without `MOTHERDUCK_TOKEN` degrade gracefully
4. `.github/workflows/stat_arb.yml`, `macro_vol.yml`, `trend_following.yml` (NEW) — matrix cron workflows per account; `timezone: "America/New_York"` on cron; `fail-fast: false` on matrix
5. `core/aggregate.py` (NEW) — post-market aggregation script writing `daily_pnl`; called by a fourth GitHub Actions workflow on a 6 PM ET cron
6. MotherDuck `trading` database — one database, all strategies separated by `strategy_name`/`account_name` columns; queried by Dives

### Critical Pitfalls

1. **Personal token in GitHub Actions** — use a dedicated service account token (Settings → Service Accounts), not a personal token. Personal token rotation silently breaks all MotherDuck writes while trades continue executing. Service account token set to non-expiring.

2. **60-day GitHub Actions auto-disable** — GitHub silently disables scheduled workflows after 60 days of repo inactivity. The trading bot may run daily but never trigger the inactivity reset. Mitigation: monitor `portfolio_snapshots` for missing days; add a data-freshness check to the aggregation Dive.

3. **Missing `strategy_name`/`account_name`/`TIMESTAMPTZ` in initial schema** — these cannot be added cleanly after data exists. Rows written before the columns were added get NULL, corrupting all cross-strategy comparisons. Define the full schema in the initial DDL. All timestamps must be `TIMESTAMPTZ` initialized with `datetime.now(timezone.utc)`.

4. **Aggregating before fills are confirmed** — strategies submit orders around 4:05 PM ET; fills are async and may take minutes to confirm. Running the aggregation at 4:30 PM produces incomplete daily P&L. Schedule aggregation at 6 PM ET; aggregate only `WHERE status = 'filled'`. Log two events: order submission and fill confirmation.

5. **Non-idempotent inserts cause duplicate records on retry** — GitHub Actions jobs can be manually re-run or auto-retried. Use `INSERT INTO trades ... ON CONFLICT (order_id) DO NOTHING` to make writes idempotent. Do not update the conflict column in a `DO UPDATE` clause (DuckDB bug #16698 corrupts rows when the conflict column is updated).

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Schema and Logger

**Rationale:** Everything else depends on data being in MotherDuck. This must ship before any workflow or Dive work begins. Creating schema incorrectly here requires destructive migration later.
**Delivers:** `core/motherduck_logger.py` with `_ensure_schema()`, `log_order()`, `snapshot_positions()`, `snapshot_portfolio()`; schema DDL for `trades`, `positions`, `portfolio_snapshots`; `duckdb` added to `requirements.txt`
**Addresses:** trades table stake, positions table stake, schema design
**Avoids:** Missing dimension columns (Pitfall 7), naive timestamps (Pitfall 6), non-idempotent inserts (Pitfall 8)
**Research flag:** No deeper research needed — MotherDuck Python API is well-documented and confirmed

### Phase 2: OrderManager and runner.py Integration

**Rationale:** Wires the logger into the execution path without touching any strategy file. Backward-compatible by design (`md_logger=None` default).
**Delivers:** Modified `core/order_manager.py` (optional `md_logger` param in all 4 order methods), modified `runner.py` (construct logger, pass to OrderManager, call snapshots after `run_cron`)
**Addresses:** Integration point at OrderManager not BaseStrategy (confirmed by architecture research)
**Avoids:** Breaking existing tests or local runs without `MOTHERDUCK_TOKEN`
**Research flag:** No deeper research needed — integration point fully mapped via code inspection

### Phase 3: GitHub Actions Workflows

**Rationale:** Moves execution from local cron to cloud. Requires Phase 1+2 to be shipping data to MotherDuck first, so workflow failures can be diagnosed via Dives.
**Delivers:** Three workflow files (`stat_arb.yml`, `macro_vol.yml`, `trend_following.yml`) with matrix jobs, `timezone: "America/New_York"` cron, `workflow_dispatch` for manual testing; GitHub Secrets configured (service account token + per-account Alpaca keys)
**Addresses:** Three workflow files not 13, per-account secret namespacing, `fail-fast: false` on matrix
**Avoids:** UTC/DST timezone errors (Pitfall 11), personal token (Pitfall 1), secret leakage via printenv (Pitfall 5), silent env fallback (Pitfall 12)
**Research flag:** No deeper research needed — GitHub Actions matrix and cron patterns are standard; `timezone:` support confirmed as of March 2026

### Phase 4: Aggregation Pipeline ("Flights" Replacement)

**Rationale:** Unblocks equity curve and strategy comparison Dives. Must run after strategy workflows are confirmed working and writing data.
**Delivers:** `core/aggregate.py` (DuckDB SQL aggregation writing `daily_pnl`), `.github/workflows/aggregate.yml` (6 PM ET cron, `MOTHERDUCK_TOKEN` only)
**Addresses:** Daily P&L aggregation, `portfolio_snapshots` rollup, `daily_pnl` table populated for Dives
**Avoids:** Aggregating before fills confirmed (Pitfall 9) — schedule at 6 PM ET, filter `WHERE status = 'filled'`
**Research flag:** No deeper research needed — aggregation SQL patterns confirmed against DuckDB docs

### Phase 5: Dives Creation

**Rationale:** Can only be done after Phases 1-4 are shipping real data. Dives are created interactively via the MotherDuck MCP tool or `MD_CREATE_DIVE` — not by code in this repo.
**Delivers:** Four persistent Dives in the MotherDuck workspace: trade log, live positions, equity curve, strategy comparison
**Addresses:** All analytics visualization table stakes
**Avoids:** Unfiltered `SELECT *` queries at scale (Pitfall 10) — all Dive queries must include a default 90-day date filter
**Research flag:** Dives creation is manual/interactive — no code to write; AI agent prompts creation via MCP. Requires Phase 1-4 data to be present first.

### Phase Ordering Rationale

- Schema first (Phase 1) because missing columns cannot be cleanly added after data exists — the strongest signal from PITFALLS.md
- Logger before workflows (Phase 2 before 3) because you need to verify data is reaching MotherDuck before trusting cron-triggered execution
- Aggregation after workflows (Phase 4 after 3) because the aggregation job only makes sense when real trade data exists to aggregate
- Dives last (Phase 5) because they read from tables — all upstream phases must be working and producing data

### Research Flags

Phases with standard patterns (no research-phase needed):
- **Phase 1:** MotherDuck Python API fully documented; DuckDB schema patterns are standard
- **Phase 2:** Integration point confirmed via direct code inspection; additive change only
- **Phase 3:** GitHub Actions matrix + cron patterns are standard; `timezone:` field confirmed March 2026
- **Phase 4:** Aggregation SQL verified against DuckDB docs; cron scheduling same as Phase 3
- **Phase 5:** Dives API well-documented; creation is interactive, not coded

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | MotherDuck Python API verified against official docs; DuckDB version lifecycle confirmed; correct pin range established |
| Features | HIGH | Dives API confirmed via official docs + Context7; "Flights" absence confirmed across all official sources; schema fields traced to Alpaca SDK |
| Architecture | HIGH | Core integration points confirmed via direct code inspection of repo; MotherDuck Python patterns from official docs |
| Pitfalls | HIGH | All pitfalls sourced from official docs, GitHub discussions, or known DuckDB bug tracker; no speculation |

**Overall confidence:** HIGH

### Gaps to Address

- **Fill confirmation logging:** The two-event pattern (submission + fill confirmation) requires a follow-up Alpaca API call to retrieve `filled_avg_price` and `filled_at`. The exact polling pattern needs to be designed during Phase 2 implementation.
- **`pnl` column in trades:** The strategy comparison Dive's win rate metric requires a `pnl` column computed at fill time in Python (pairing entry and exit prices). This column needs to be added to the Phase 1 schema DDL and the logger updated to compute it.
- **60-day inactivity mitigation:** No automated solution is in scope. The roadmap should include a task to set a calendar reminder or add a data-freshness Dive alert, but implementation is deferred to Phase 5 or post-launch.

---

## Sources

### Primary (HIGH confidence)
- MotherDuck Python authentication + connection: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/connecting-to-motherduck/
- MotherDuck Dives documentation: https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/
- MD_CREATE_DIVE SQL function: https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/
- MotherDuck service accounts: https://motherduck.com/docs/key-tasks/service-accounts-guide/
- MotherDuck version lifecycle: https://motherduck.com/docs/troubleshooting/version-lifecycle-schedules/
- MotherDuck GitHub Actions cron pattern: https://motherduck.com/docs/key-tasks/data-warehousing/orchestration/github-action-cron
- DuckDB window functions: https://duckdb.org/docs/current/sql/functions/window_functions
- DuckDB concurrency: https://duckdb.org/docs/current/connect/concurrency
- DuckDB ON CONFLICT bug #16698: https://github.com/duckdb/duckdb/issues/16698
- GitHub Actions matrix: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow
- GitHub Actions secrets: https://docs.github.com/en/actions/security-guides/encrypted-secrets

### Secondary (MEDIUM confidence)
- MotherDuck scheduled queries feature request (in progress, not released): https://motherduck.canny.io/feature-requests/p/scheduled-queries-notebooks
- GitHub Actions 60-day inactivity: https://github.com/fischerscode/DockerFlutter/issues/50
- GitHub Actions cron drift behavior: https://crontap.com/blog/github-actions-cron-drift-problem
- Alpaca Order model fields: https://alpaca.markets/sdks/python/api_reference/trading/models.html

---
*Research completed: 2026-06-02*
*Ready for roadmap: yes*
