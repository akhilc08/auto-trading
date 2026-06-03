---
phase: 1
slug: schema-logger-integration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-03
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (in `.venv`) |
| **Config file** | none — pytest auto-discovers `tests/` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_motherduck_logger.py tests/test_order_manager_logging.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~2 seconds (all tests use in-memory DuckDB / mocks — no network) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, SCHEMA-09, SCHEMA-10 | T-01-SC | duckdb pinned `==1.5.2` (audited [OK]); failing tests describe full logger contract (RED) | unit | `grep -qx 'duckdb==1.5.2' requirements.txt && .venv/bin/python -m pytest tests/test_motherduck_logger.py -q` | ❌ W0 | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, SCHEMA-09, SCHEMA-10 | T-01-01 / T-01-02 / T-01-03 | All SQL parameterized (`?` placeholders); `ON CONFLICT DO NOTHING` only; float casts with None guards; no import-time connection | unit | `.venv/bin/python -m pytest tests/test_motherduck_logger.py -q` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | INTEG-01, INTEG-02 | T-01-06 | log_order called in all 5 order methods (incl. close_position which returns an Order); backward compatible; no strategies/ file touched | unit | `.venv/bin/python -m pytest tests/test_order_manager_logging.py tests/test_live_execution.py -q` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | INTEG-03, INTEG-04, INTEG-05, INTEG-06 | T-01-04 / T-01-05 / T-01-06 | Token read only via `os.environ.get`; logger constructed only when present; try/finally snapshot; pnl=None valid (SCHEMA-07 nullable); strategies/ + scheduler.py untouched | smoke (parse + grep) | `.venv/bin/python -c "import ast; ast.parse(open('runner.py').read())" && grep -q 'MOTHERDUCK_TOKEN' runner.py && grep -q 'finally:' runner.py` | ✅ existing (runner.py) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_motherduck_logger.py` — stub with 7 failing tests for SCHEMA-01..10 (`test_no_token_no_exception`, `test_schema_creates_all_tables`, `test_idempotent_insert`, `test_log_order_none_is_noop`, `test_update_fill`, `test_snapshot_positions`, `test_snapshot_portfolio`) using in-memory DuckDB (`duckdb.connect()` with no `"md:"`, injected via `MotherDuckLogger(con=...)`)
- [ ] `tests/test_order_manager_logging.py` — stub with 7 failing tests for INTEG-01/INTEG-02 (`test_backward_compat_no_md_logger`, `test_buy_logs_order`, `test_sell_logs_order`, `test_short_sell_logs_order`, `test_buy_to_cover_logs_order`, `test_close_position_logs_order`, `test_log_order_receives_strategy_and_account`) using `_RecordingLogger` + `MockClient` stubs
- [ ] `duckdb==1.5.2` install into `.venv` (`.venv/bin/pip install duckdb==1.5.2`) — required before any logger test can run

*Both new test files are created in the RED step of their owning TDD tasks (01-01-T1 and 01-02-T1) at execution time. pytest framework already present in `.venv`; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No strategy file modified | INTEG-06 | git-state check, not a unit test | Run `git diff --name-only HEAD -- strategies/ core/scheduler.py` — output must be empty |
| Live MotherDuck write against real `md:` connection | SCHEMA-05 (live path) | Requires real `MOTHERDUCK_TOKEN`; unit tests use in-memory DuckDB | With token set, run `runner.py` once and confirm rows appear in `trading.main.trades` via MotherDuck SQL |

*All in-process phase behaviors have automated verification; the two above require git state or live credentials.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (all 4 tasks have automated commands)
- [x] Wave 0 covers all MISSING references (both new test files listed)
- [x] No watch-mode flags (all commands are single-shot `-q` runs)
- [x] Feedback latency < ~2s (in-memory DuckDB / mocks, no network)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-03
