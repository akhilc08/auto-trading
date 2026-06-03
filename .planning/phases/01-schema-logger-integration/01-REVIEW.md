---
phase: 01-schema-logger-integration
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - core/motherduck_logger.py
  - core/order_manager.py
  - runner.py
  - tests/test_motherduck_logger.py
  - tests/test_order_manager_logging.py
  - tests/test_live_execution.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Six files reviewed: the new `MotherDuckLogger` write layer, `OrderManager` integration, the `runner.py` entry-point, and three test modules. All 14 tests pass. The core logging logic is structurally sound — idempotent inserts, schema creation, and `md_logger` optional-injection are all correct.

Two bugs require attention before this ships. The most impactful is a falsy-zero data-corruption bug in `snapshot_positions` and `snapshot_portfolio`: numeric `0.0` values for `current_price`, `unrealized_pl`, `equity`, `cash`, and `buying_power` are silently recorded as `NULL` instead of `0.0`. This can happen when the market is closed and positions are flat. The second is that the `runner.py` shutdown data-flush has no error handling inside the `finally` block, so a single API failure during shutdown aborts all subsequent snapshot/fill logging with no warning.

---

## Critical Issues

### CR-01: Falsy-zero check converts valid `0.0` fields to `NULL`

**File:** `core/motherduck_logger.py:128-129, 144-146`

**Issue:** `snapshot_positions` and `snapshot_portfolio` use truthiness to guard `float()` conversion:

```python
float(position.current_price) if position.current_price else None
float(position.unrealized_pl) if position.unrealized_pl else None
float(account.equity) if account.equity else None
```

If the Alpaca SDK ever returns a numeric `0` or `0.0` for any of these fields (e.g., `equity=0.0` during account suspension, `unrealized_pl=0.0` for a flat position at entry price, `buying_power=0.0` when fully invested), the value is silently written as `NULL` instead of `0.0`. String `"0"` and `"0.0"` are truthy so they survive, but the guard is wrong for any numeric path, including `float` coercions the SDK may perform in future versions.

The correct guard is an explicit `None` check:

```python
# snapshot_positions — lines 128-129
float(position.current_price) if position.current_price is not None else None,
float(position.unrealized_pl) if position.unrealized_pl is not None else None,

# snapshot_portfolio — lines 144-146
float(account.equity) if account.equity is not None else None,
float(account.cash) if account.cash is not None else None,
float(account.buying_power) if account.buying_power is not None else None,
```

---

## Warnings

### WR-01: `runner.py` finally block has no error handling — one API failure aborts all shutdown logging

**File:** `runner.py:82-99`

**Issue:** The shutdown data-flush runs as a linear sequence inside `finally` with no `try/except`:

```python
finally:
    if md_logger:
        positions = client.trading.get_all_positions()          # if this raises...
        md_logger.snapshot_positions(...)                       # these never run
        account = client.trading.get_account()
        md_logger.snapshot_portfolio(...)
        orders = client.trading.get_orders(...)
        for o in orders:
            md_logger.update_fill(...)
```

If `get_all_positions()` raises (Alpaca API error, network timeout after a crash), the exception propagates out of the `finally` block. No snapshot and no fill records are written. Because the `finally` is triggered on normal shutdown, `KeyboardInterrupt`, and crashes alike, this silent data loss is most likely when data is most needed (after a strategy crash).

**Fix:** Wrap each independent flush step in its own `try/except`:

```python
finally:
    if md_logger:
        try:
            positions = client.trading.get_all_positions()
            md_logger.snapshot_positions(positions, args.strategy, account_name)
        except Exception as e:
            logger.error(f"Shutdown: snapshot_positions failed: {e}")
        try:
            account = client.trading.get_account()
            md_logger.snapshot_portfolio(account, args.strategy, account_name)
        except Exception as e:
            logger.error(f"Shutdown: snapshot_portfolio failed: {e}")
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            import datetime as dt
            today = dt.date.today()
            orders = client.trading.get_orders(GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                after=dt.datetime.combine(today, dt.time.min, tzinfo=dt.timezone.utc),
            ))
            for o in orders:
                if o.filled_at and o.filled_avg_price:
                    md_logger.update_fill(str(o.id), o.filled_at, float(o.filled_avg_price), None)
        except Exception as e:
            logger.error(f"Shutdown: fill polling failed: {e}")
```

---

### WR-02: `close_position` is missing `return None` in its exception path

**File:** `core/order_manager.py:95-104`

**Issue:** Every other order method (`buy`, `sell`, `short_sell`, `buy_to_cover`) has an explicit `return None` in the `except` block. `close_position` relies on Python's implicit `None` return, which is functionally equivalent but creates an inconsistency. More importantly, the test `test_close_position_logs_order` asserts `rec.calls[0][0] is order` — it only tests the success path. If the Alpaca call raises, the caller gets `None` from `close_position` with no indication other than the logged error. The inconsistency with the other four methods makes this a maintenance trap.

**Fix:**
```python
    def close_position(self, symbol: str):
        try:
            self.logger.info(f"Closing position {symbol}")
            order = self.client.trading.close_position(symbol)
            self.logger.info(f"Position closed {symbol}")
            if self.md_logger:
                self.md_logger.log_order(order, self.strategy_name, self.account_name)
            return order
        except Exception as e:
            self.logger.error(f"Close position failed {symbol}: {e}")
            return None   # add this line
```

---

### WR-03: `update_fill` silently no-ops when `order_id` was never logged

**File:** `runner.py:97-99`, `core/motherduck_logger.py:101-108`

**Issue:** `runner.py`'s shutdown loop calls `update_fill` for every closed order returned by `get_orders` today, regardless of whether those orders were ever inserted into `trading.main.trades` by `log_order`. If a strategy was started without a `MOTHERDUCK_TOKEN` (so `log_order` was never called), or if the same orders appear across multiple runner invocations on the same day, `UPDATE ... WHERE order_id = ?` matches zero rows and silently succeeds. No row count is checked, no warning is emitted. This means fills can be permanently lost without any indication.

**Fix:** Either add a rowcount check after the update, or use an `INSERT ... ON CONFLICT DO UPDATE` (upsert) in `update_fill` so a fill record is created even when `log_order` was never called:

```python
def update_fill(self, order_id: str, filled_at, filled_avg_price, pnl):
    self.con.execute(
        """
        UPDATE trading.main.trades
        SET filled_at = ?, filled_avg_price = ?, pnl = ?, status = 'filled'
        WHERE order_id = ?
        """,
        [filled_at, filled_avg_price, pnl, order_id],
    )
    # Caller should check rowcount if silent no-op is not acceptable
```

At minimum, `runner.py` should log a warning when `update_fill` is called for an order that is not in the table. The cleanest fix is a rowcount check in `update_fill` itself, surfacing the gap as a warning.

---

### WR-04: `test_no_token_no_exception` does not test the SCHEMA-10 guarantee it claims to

**File:** `tests/test_motherduck_logger.py:57-71`

**Issue:** The test comment says it verifies "graceful degradation when MOTHERDUCK_TOKEN is absent," but the test body only verifies that the module can be imported without error — something that is already proven by the `from core.motherduck_logger import MotherDuckLogger` at the top of the file. The `importlib.reload` call does not test construction with no token; `MotherDuckLogger(token=None)` would raise a `duckdb.InvalidInputException` (confirmed at runtime). The actual SCHEMA-10 protection is in `runner.py`'s `if token:` guard, which has no test at all.

**Fix:** Either add a test that constructs `MotherDuckLogger()` (no args, no injected connection) and asserts it raises a clear exception, or add a test that simulates the `runner.py` path with `token=None` and asserts `md_logger` is `None`. Rename the existing test to `test_import_does_not_connect` to accurately describe what it does.

---

## Info

### IN-01: Imports inside `finally` block should be at module level

**File:** `runner.py:89-92`

**Issue:** `GetOrdersRequest`, `QueryOrderStatus`, and `datetime` are imported inside the `finally` block. This is functional but unusual — it obscures dependencies and makes the code harder to read. The `datetime` alias `dt` also introduces a name (`dt`) that only exists in the `finally` scope, which is unconventional.

**Fix:** Move these three imports to the top of `runner.py` alongside the other imports. Rename `dt` to `datetime` (or keep the alias and move it to module level).

---

### IN-02: `_ensure_schema` silently swallows all exceptions from `CREATE DATABASE`

**File:** `core/motherduck_logger.py:25-28`

**Issue:** The `except Exception:` block catches any error from `CREATE DATABASE IF NOT EXISTS trading` and falls back to `ATTACH`. In production against a live MotherDuck connection, a real failure (e.g., permission denied, quota exceeded) would silently fall back to attaching a local `:memory:` database, and all subsequent writes would succeed locally but never reach MotherDuck. The data loss would be invisible.

**Fix:** Narrow the catch to only `duckdb.ParserException` (the exception raised when `CREATE DATABASE` is not supported syntax — confirmed in DuckDB 1.5.2):

```python
try:
    self.con.execute("CREATE DATABASE IF NOT EXISTS trading")
except duckdb.ParserException:
    self.con.execute("ATTACH IF NOT EXISTS ':memory:' AS trading")
```

This ensures unexpected errors from a real MotherDuck connection propagate instead of silently redirecting writes to an in-memory DB.

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
