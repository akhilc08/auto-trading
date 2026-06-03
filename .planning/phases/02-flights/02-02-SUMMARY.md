---
phase: 02-flights
plan: 02
subsystem: execution-flights
tags: [flights, alpaca, execution, motherduck, packaging]
requires: [02-01]
provides:
  - "flights/exec/_runner.run_account_flight (reusable execution scaffold) — used by 02-03"
  - "flights/exec/_logger.FlightLogger (bundled write layer)"
  - "exec-stat-arb live MotherDuck Flight"
  - "repo is pip-installable (pyproject.toml) — Flights install it via GitHub tarball URL"
affects: [02-03-exec-flights-macro-trend]
tech-stack:
  added: []
  patterns:
    - "MotherDuck Flights are single-file; install multi-file repo code via 'auto-trading @ https://github.com/<owner>/<repo>/archive/<sha>.tar.gz' (uv has NO git, so git+ URLs fail)"
    - "Execution Flights read Alpaca creds from a PERSISTENT MotherDuck secret (storage=motherduck) — session-memory secrets are invisible to the Flight connection"
    - "IEX feed (not SIP) for Alpaca bar fetches on the free data tier"
key-files:
  created:
    - flights/exec/_logger.py
    - flights/exec/_runner.py
    - flights/exec/exec_stat_arb.py
    - flights/exec/requirements.txt
    - flights/exec/__init__.py
    - flights/__init__.py
    - pyproject.toml
  modified:
    - flights/secrets/create_secrets.sql
    - flights/secrets/README.md
key-decisions:
  - "Flight packaging: a MotherDuck Flight is a single source_code file; the build env (uv) has NO git. Resolved by making the repo pip-installable (pyproject.toml) and installing it via the GitHub HTTPS tarball URL pinned to a commit SHA. Repo made public."
  - "Secrets MUST be PERSISTENT: a plain CREATE SECRET is session-memory (storage=memory) and invisible to the Flight's separate duckdb.connect('md:'). CREATE PERSISTENT SECRET stores in MotherDuck cloud (storage=motherduck). Fixed 02-01's template + README too."
  - "IEX data feed: Alpaca paper plan blocks recent SIP data (403). Added _IEXAlpacaClient subclass in the Flight runner overriding get_latest_bars/get_historical_bars with feed=IEX, so every strategy data call uses IEX. core/ left unmodified per plan constraint."
  - "Reused core.OrderManager/AlpacaClient/BaseStrategy (installed via the package) rather than reimplementing; FlightLogger reimplements the Phase 1 write contracts inline per the plan's acceptance criteria."
requirements-completed: [EXEC-01, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08, SECRETS-02, SECRETS-03]
duration: "~50 min"
completed: "2026-06-03"
---

# Phase 02 Plan 02: exec-stat-arb Execution Flight Summary

Reusable single-file MotherDuck execution-Flight scaffold + the live `exec-stat-arb` Flight running the five stat_arb-account strategies on MotherDuck compute, reading Alpaca creds from a persistent secret and writing to MotherDuck via a bundled logger.

## What Was Built
- **`flights/exec/_logger.py`** — `FlightLogger`: idempotent DDL + log_order (ON CONFLICT DO NOTHING) / update_fill / snapshot_positions / snapshot_portfolio.
- **`flights/exec/_runner.py`** — `run_account_flight(account, strategies, secret)`: reads the persistent secret, builds an IEX-feed Alpaca client, market-hours guard, strategy discovery + on_bar, fill polling, snapshots. Includes `_IEXAlpacaClient`.
- **`flights/exec/exec_stat_arb.py`** — entrypoint wiring the 5 stat_arb strategies + `alpaca_stat_arb`.
- **`pyproject.toml` + `__init__.py`s** — make the repo pip-installable so a single-file Flight can import `flights/`, `core/`, `strategies/`.
- **Live Flight `exec-stat-arb`** (id a5c7c980-…): cron `5 20 * * 1-5` (16:05 ET summer; winter `5 21 * * 1-5`), token `MotherDuck Extension`.

## Deployed Flight requirements_txt (not the repo file — records the tarball install)
```
duckdb==1.5.2
auto-trading @ https://github.com/akhilc08/auto-trading/archive/<commit-sha>.tar.gz
```

## Verification (live, run #4 SUCCEEDED, exit 0)
- Install + import + execution all succeeded; all 5 strategies ran cointegration/factor formation with real IEX data.
- `portfolio_snapshots`: 5 rows per run, `account_name='stat_arb'`, real paper balance ($99,999.45) — write path proven (EXEC-04/05, SECRETS-02/03).
- `trades`: 0 this run — strategies completed formation but no entry signal fired on the single on_bar call (expected; not a failure). Orders go through `OrderManager` → `log_order`, so they will be captured when a signal fires.

## Deviations from Plan
**[Rule 4 — architectural, user-approved]** The plan assumed a Flight could "bundle strategies/ + core/" as multiple files. A MotherDuck Flight is a SINGLE source file and the build env has no git. Resolved (with user decisions) by: making the repo pip-installable + public and installing it via the GitHub tarball URL. Added pyproject.toml + __init__.py (new scope).
**[Rule 2 — missing critical]** Plain `CREATE SECRET` (from 02-01) is session-memory and invisible to the Flight; switched to `CREATE PERSISTENT SECRET` and recreated all three secrets. Fixed 02-01 artifacts too.
**[Rule 2 — missing critical]** Alpaca paper plan blocks recent SIP data (403); added `_IEXAlpacaClient` (IEX feed) in the Flight runner. `core/` untouched.

**Total deviations:** 3 (1 architectural/approved, 2 missing-critical auto-fixes). **Impact:** Flight is deployable and runs green; required public repo + packaging.

## Open / Deferred
- **Trade capture** depends on a strategy entry signal firing (none did this bar) — will be exercised by the scheduled 16:05 ET run.
- **Market-closed guard** (`get_clock().is_open` early return) is code-verified but not yet live-tested with a closed market (the scheduled weekday run / a weekend run will exercise it).
- Two pre-existing Alpaca paper orders from today are not in `trades` (not placed by this Flight) → benign "fill record lost" warnings.
- Production should use a dedicated **service-account** token rather than `MotherDuck Extension` (PITFALLS #1).

## Self-Check: PASSED
- key-files exist; commits present (8eef7a2, 9b6355e, 0e32a60, 9820d34); Task 1/2 acceptance verifies PASS; live run #4 exit 0.

## Next
Scaffold is reusable by 02-03 (exec-macro-vol, exec-trend-following are thin entrypoints). 02-04 (aggregation) is independent and ready to deploy.
