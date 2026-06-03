---
phase: 01-schema-logger-integration
plan: "01"
subsystem: core
tags: [duckdb, motherduck, schema, logger, tdd]
dependency_graph:
  requires: []
  provides: [core/motherduck_logger.py, trading.main.trades, trading.main.positions, trading.main.portfolio_snapshots, trading.main.daily_pnl]
  affects: []
tech_stack:
  added: [duckdb==1.5.2]
  patterns: [parameterized-sql, constructor-injection, try-except-db-create]
key_files:
  created:
    - core/motherduck_logger.py
    - tests/test_motherduck_logger.py
  modified:
    - requirements.txt
decisions:
  - "ATTACH fallback: _ensure_schema() tries CREATE DATABASE IF NOT EXISTS trading (MotherDuck DDL) then falls back to ATTACH IF NOT EXISTS ':memory:' AS trading for in-memory DuckDB used in tests"
  - "Constructor injection: MotherDuckLogger(con=...) accepts a pre-built DuckDB connection to enable in-memory testing without a live MotherDuck token"
  - "daily_pnl columns use REQUIREMENTS.md SCHEMA-04 (date, strategy_name, account_name PK, realized_pnl, trade_count, win_count, sharpe_7d, max_drawdown)"
metrics:
  duration: "4m"
  completed: "2026-06-03"
  tasks_completed: 2
  files_changed: 3
---

# Phase 01 Plan 01: MotherDuck Logger Schema Summary

MotherDuckLogger class with 4-table idempotent DDL, parameterized writes, and in-memory DuckDB test injection using ATTACH fallback.

## What Was Built

Created `core/motherduck_logger.py` — the single write choke point for all MotherDuck data. The class:

- Runs `CREATE TABLE IF NOT EXISTS` DDL for all 4 tables (`trades`, `positions`, `portfolio_snapshots`, `daily_pnl`) on construction
- Accepts either a `token` (live MotherDuck) or `con` (injected DuckDB connection for tests)
- Uses parameterized `?` placeholders throughout — no f-string SQL
- Imports cleanly with no side effects when no token is present (SCHEMA-10)

Pinned `duckdb==1.5.2` in `requirements.txt` and installed it in the project venv.

## TDD Gate Compliance

- RED commit `e77b0ba`: `test(01-01): pin duckdb==1.5.2 and add failing tests for MotherDuckLogger (RED)` — 7 tests that fail with `ModuleNotFoundError` on import
- GREEN commit `cbe87a2`: `feat(01-01): implement MotherDuckLogger with schema DDL and write methods (GREEN)` — all 7 tests pass
- No REFACTOR step needed; implementation is clean at ~115 lines

## Schema Columns (final)

### trades (SCHEMA-01)
`order_id` (PK), `strategy_name`, `account_name`, `symbol`, `side`, `qty DECIMAL(18,4)`, `submitted_at TIMESTAMPTZ`, `filled_at TIMESTAMPTZ`, `filled_avg_price DECIMAL(18,4)`, `pnl DECIMAL(18,4)`, `status DEFAULT 'submitted'`

### positions (SCHEMA-02)
`snapshot_at TIMESTAMPTZ`, `strategy_name`, `account_name`, `symbol`, `qty DECIMAL(18,4)`, `avg_entry_price DECIMAL(18,4)`, `current_price DECIMAL(18,4)`, `unrealized_pnl DECIMAL(18,4)` — NOTE: Alpaca SDK field is `unrealized_pl` (no `n`), mapped to column `unrealized_pnl`

### portfolio_snapshots (SCHEMA-03)
`snapshot_at TIMESTAMPTZ`, `strategy_name`, `account_name`, `equity DECIMAL(18,4)`, `cash DECIMAL(18,4)`, `buying_power DECIMAL(18,4)`

### daily_pnl (SCHEMA-04 — REQUIREMENTS.md authoritative)
`date DATE`, `strategy_name`, `account_name` (composite PK), `realized_pnl DECIMAL(18,4)`, `trade_count INTEGER`, `win_count INTEGER`, `sharpe_7d DECIMAL(18,6)`, `max_drawdown DECIMAL(18,6)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `CREATE DATABASE IF NOT EXISTS trading` not supported in DuckDB 1.5.2 in-memory**
- **Found during:** Task 2 — first GREEN run
- **Issue:** `duckdb.connect()` (in-memory) raises `ParserException: syntax error at or near "DATABASE"` for `CREATE DATABASE IF NOT EXISTS trading`. This is MotherDuck-specific DDL, not standard DuckDB.
- **Fix:** `_ensure_schema()` wraps the call in try/except. On success it uses the MotherDuck DDL. On `ParserException`, it falls back to `ATTACH IF NOT EXISTS ':memory:' AS trading` which creates the `trading` database catalog in the in-memory connection. Both paths produce a `trading` catalog that the subsequent `CREATE TABLE IF NOT EXISTS trading.main.<table>` statements target correctly.
- **Files modified:** `core/motherduck_logger.py` — `_ensure_schema()` method
- **Commit:** `cbe87a2` (included in GREEN commit)

## Known Stubs

None. The logger is fully wired — all 5 methods write real SQL to the DuckDB connection.

## Threat Surface Scan

No new surface beyond what the plan's threat model covers:
- T-01-01 (MOTHERDUCK_TOKEN): token only via `duckdb.connect("md:", config={...})`; never logged
- T-01-02 (DuckDB writes): all `con.execute` calls use `?` parameterized placeholders
- T-01-03 (numeric casts): all Alpaca string fields cast via `float()` with None guards before insert

## Self-Check: PASSED

- `core/motherduck_logger.py` exists: FOUND
- `tests/test_motherduck_logger.py` exists: FOUND
- `requirements.txt` contains `duckdb==1.5.2`: FOUND
- Task 1 commit `e77b0ba`: FOUND
- Task 2 commit `cbe87a2`: FOUND
- All 7 tests pass: CONFIRMED (82 total, 0 failures)
