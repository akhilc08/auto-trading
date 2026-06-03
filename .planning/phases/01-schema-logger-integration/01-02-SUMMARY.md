---
phase: 01-schema-logger-integration
plan: "02"
subsystem: core
tags: [order-manager, runner, motherduck, tdd, integration]
dependency_graph:
  requires: [01-01]
  provides: [core/order_manager.py (md_logger integration), runner.py (logger wiring + snapshots)]
  affects: [runner.py, core/order_manager.py]
tech_stack:
  added: []
  patterns: [optional-param-injection, try-finally-cleanup, conditional-import, tdd-red-green]
key_files:
  created:
    - tests/test_order_manager_logging.py
    - tests/test_live_execution.py
  modified:
    - core/order_manager.py
    - runner.py
decisions:
  - "OrderManager accepts md_logger/strategy_name/account_name as __init__ params with defaults — existing callers unchanged (INTEG-01)"
  - "MotherDuckLogger imported conditionally inside main() so module has no side effects when token is absent (SCHEMA-10)"
  - "try/finally wraps run_cron/run_stream so snapshot+fill-poll fires at process exit — correct for blocking APScheduler (Pitfall 1)"
  - "pnl=None passed to update_fill in Phase 1 — trades.pnl is NULLABLE per SCHEMA-07; realized P&L deferred to Phase 2 daily_pnl Flight"
metrics:
  duration: "8m"
  completed: "2026-06-03"
  tasks_completed: 2
  files_changed: 4
---

# Phase 01 Plan 02: OrderManager + runner.py Integration Summary

OrderManager gains md_logger/strategy_name/account_name optional params with log_order calls in all 5 order methods; runner.py constructs MotherDuckLogger conditionally and snapshots positions/portfolio + polls fills in a try/finally.

## What Was Built

### core/order_manager.py

Changed `__init__` signature from `(self, client, logger)` to `(self, client, logger, md_logger=None, strategy_name="", account_name="")`. Backward compatible — all existing callers that omit the new params continue to work unchanged.

Added `if self.md_logger: self.md_logger.log_order(order, self.strategy_name, self.account_name)` after the successful submission log line in all 5 order methods:

| Method | Insertion point |
|--------|----------------|
| `buy` | After `logger.info("BUY submitted order_id=...")`, before `return order` |
| `sell` | After `logger.info("SELL submitted order_id=...")`, before `return order` |
| `short_sell` | After `logger.info("SHORT submitted order_id=...")`, before `return order` |
| `buy_to_cover` | After `logger.info("COVER submitted order_id=...")`, before `return order` |
| `close_position` | After `logger.info("Position closed ...")` — also captures the `Order` returned by `client.trading.close_position(symbol)` (SDK returns `Order(**response)`) and returns it |

`close_position` now returns the captured `Order` (previously returned `None` implicitly). This is the 5th log_order site per INTEG-02.

### runner.py

- Added `import os` to stdlib block
- `account_name = account_for(args.strategy)` computed before OrderManager construction
- Conditional MotherDuckLogger construction: `token = os.environ.get("MOTHERDUCK_TOKEN")` — import and instantiate only when present: `MotherDuckLogger(token=token)` (keyword arg matches constructor signature from Plan 01)
- `OrderManager` construction now passes `md_logger=md_logger, strategy_name=args.strategy, account_name=account_name`
- `run_cron`/`run_stream` wrapped in `try/finally`; `finally` block guarded by `if md_logger:` and:
  - `snapshot_positions(positions, strategy, account_name)`
  - `snapshot_portfolio(account, strategy, account_name)`
  - Fill poll: `GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=today_utc)` → `update_fill(id, filled_at, filled_avg_price, None)`

### MotherDuckLogger constructor call used

`MotherDuckLogger(token=token)` — matches the Plan 01 constructor `def __init__(self, token: str = None, con=None)`.

### tests/test_order_manager_logging.py (new)

7 tests:
- `test_backward_compat_no_md_logger` — confirms `OrderManager(client=..., logger=...)` still works
- `test_buy_logs_order`, `test_sell_logs_order`, `test_short_sell_logs_order`, `test_buy_to_cover_logs_order` — each asserts one `log_order` call with the returned order
- `test_close_position_logs_order` — asserts log_order called with the Order the SDK returns
- `test_log_order_receives_strategy_and_account` — asserts strategy_name/account_name injected via __init__

### tests/test_live_execution.py (brought in)

Live-execution regression tests that existed in the main repo as untracked. Committed here to satisfy the plan's backward-compat verification requirement. These tests use `OrderManager(client=client, logger=_NullLogger())` (old signature) — confirm backward compat holds.

Note: 6 tests in this file fail against the current strategy implementations (pre-existing bugs in market_neutral, multi_factor, trend_following, pead, stat_arb). These failures are unrelated to OrderManager and out of scope for this plan.

## TDD Gate Compliance

- RED commit `65d34aa`: `test(01-02): add failing tests for OrderManager md_logger integration (RED)` — 6 tests fail with `TypeError: unexpected keyword argument 'md_logger'`
- GREEN commit `fd41a0c`: `feat(01-02): add md_logger to OrderManager with log_order in all 5 methods (GREEN)` — all 7 tests pass

## Strategy/Scheduler File Integrity

`git diff --name-only HEAD strategies/ core/scheduler.py` is empty — INTEG-06 confirmed.

## Deviations from Plan

### Out-of-scope pre-existing failures documented

**[Scope Boundary] test_live_execution.py strategy failures**
- **Found during:** Task 1 verification
- **Issue:** 6 tests in `test_live_execution.py` fail against current strategy implementations (market_neutral, multi_factor, trend_following, pead, stat_arb). These tests document pre-existing bugs in strategy behavior unrelated to OrderManager.
- **Action:** Documented in deferred-items.md; not fixed per scope boundary rule. The `_build()` helper (line 98) uses `OrderManager(client=client, logger=_NullLogger())` — confirms backward compat signature works with no TypeError.
- **Impact:** Zero — all OrderManager tests (7 new) pass; the strategy failures were present before this plan.

## Known Stubs

None. All 5 log_order call sites are wired to the real MotherDuckLogger. runner.py snapshot/fill-poll calls the real methods.

## Threat Surface Scan

No new surface beyond the plan's threat model:
- T-01-04 (token read): `os.environ.get("MOTHERDUCK_TOKEN")` only; never passed to any log call
- T-01-05 (finally block): snapshot/fill-poll at process exit only; Alpaca failures surface on shutdown, do not affect trading
- T-01-06 (strategy integrity): confirmed `git diff HEAD strategies/` is empty

## Self-Check: PASSED

- `core/order_manager.py` modified: FOUND
- `tests/test_order_manager_logging.py` created: FOUND
- `tests/test_live_execution.py` created: FOUND
- `runner.py` modified: FOUND
- RED commit `65d34aa`: FOUND
- GREEN commit `fd41a0c`: FOUND
- runner.py commit `3a13364`: FOUND
- `grep -c 'self.md_logger.log_order' core/order_manager.py` returns 5: CONFIRMED
- All 7 new tests pass: CONFIRMED (14 total with logger tests, 0 failures in scope)
- `git diff HEAD strategies/` empty: CONFIRMED
