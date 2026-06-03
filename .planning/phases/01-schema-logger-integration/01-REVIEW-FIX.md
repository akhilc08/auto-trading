---
phase: 01-schema-logger-integration
fixed_at: 2026-06-03T00:00:00Z
review_path: .planning/phases/01-schema-logger-integration/01-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-06-03T00:00:00Z
**Source review:** .planning/phases/01-schema-logger-integration/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Falsy-zero check converts valid `0.0` fields to `NULL`

**Files modified:** `core/motherduck_logger.py`
**Commit:** d30414c
**Applied fix:** Changed five truthiness guards (`if field else None`) to explicit `None` checks (`if field is not None else None`) in `snapshot_positions` (lines 128-129) and `snapshot_portfolio` (lines 144-146). This ensures numeric `0.0` values are stored correctly instead of silently becoming `NULL`.

---

### WR-01: `runner.py` finally block has no error handling

**Files modified:** `runner.py`
**Commit:** 25bf657
**Applied fix:** Wrapped each of the three independent shutdown flush operations (snapshot_positions, snapshot_portfolio, fill polling) in its own `try/except Exception` block with `logger.error(...)` on failure. A single API failure during shutdown no longer aborts the remaining flush steps.

---

### WR-02: `close_position` missing `return None` in exception path

**Files modified:** `core/order_manager.py`
**Commit:** 2d65dcc
**Applied fix:** Added explicit `return None` in the `except` block of `close_position`, matching the pattern used by `buy`, `sell`, `short_sell`, and `buy_to_cover`.

---

### WR-03: `update_fill` silently no-ops when `order_id` was never logged

**Files modified:** `core/motherduck_logger.py`
**Commit:** 2965558
**Applied fix:** Changed the UPDATE statement to use `RETURNING order_id` and added a `warnings.warn(RuntimeWarning)` when the returned rows list is empty. Also added `import warnings` at module level. DuckDB supports `UPDATE ... RETURNING`, and an empty result set reliably indicates zero rows matched. This surfaces the "fill record lost" condition as a visible warning rather than a silent no-op.

---

### WR-04: `test_no_token_no_exception` does not test the SCHEMA-10 guarantee

**Files modified:** `tests/test_motherduck_logger.py`
**Commit:** 470ae2d
**Applied fix:** Renamed `test_no_token_no_exception` to `test_import_does_not_connect` with an accurate docstring. Added a new test `test_no_token_skips_md_logger` that mirrors the `runner.py` `if token:` guard and asserts `md_logger` remains `None` when `MOTHERDUCK_TOKEN` is absent (skips when the token is set in CI).

---

_Fixed: 2026-06-03T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
