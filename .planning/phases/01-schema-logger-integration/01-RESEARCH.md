# Phase 1: Schema, Logger & Integration - Research

**Researched:** 2026-06-03
**Domain:** DuckDB/MotherDuck Python integration, Alpaca SDK models, core/ module wiring
**Confidence:** HIGH

## Summary

Phase 1 creates the data pipeline foundation for the entire v1.0 milestone. The work is
minimal in scope: one new file (`core/motherduck_logger.py`), two small edits
(`core/order_manager.py`, `runner.py`), and one line added to `requirements.txt`. No
strategy file is touched.

The existing codebase is clean and well-structured. `OrderManager` already has 5 order
methods (buy, sell, short_sell, buy_to_cover, close_position) — all 5 need a single
`md_logger.log_order()` call after a successful submission. The `runner.py` constructs
`OrderManager` and calls `run_cron()` in a single synchronous block — both integration
points (construct logger before `OrderManager`, call snapshots after `run_cron`) are
obvious and localized.

The Alpaca SDK models are confirmed. `Order.id` (UUID), `Order.symbol`, `Order.side`,
`Order.qty` (str), `Order.submitted_at` (datetime), `Order.filled_at` (Optional[datetime]),
`Order.filled_avg_price` (Optional[str|float]), `Order.status` (OrderStatus enum).
`Position` model: `symbol`, `qty` (str), `avg_entry_price` (str), `current_price`
(Optional[str]), `unrealized_pl` (Optional[str]). `TradeAccount` model: `equity`
(Optional[str]), `cash` (Optional[str]), `buying_power` (Optional[str]). All numeric
fields from Alpaca come as strings — cast to float before inserting into DuckDB.

**Primary recommendation:** Create `core/motherduck_logger.py` first with `_ensure_schema()`
creating all 4 tables. Then edit `OrderManager` to accept `md_logger=None` and call
`log_order()` in all 5 methods. Then edit `runner.py` to wire in the logger and call
snapshots + fill poll after `run_cron()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHEMA-01 | `trades` table with specified columns | DDL confirmed. `order_id` as VARCHAR PRIMARY KEY (UUID str). All TIMESTAMPTZ. |
| SCHEMA-02 | `positions` table with specified columns | DDL confirmed. `snapshot_at` TIMESTAMPTZ, no PK (append-only snapshots). |
| SCHEMA-03 | `portfolio_snapshots` table with specified columns | DDL confirmed. `snapshot_at` TIMESTAMPTZ, no PK (append-only snapshots). |
| SCHEMA-04 | `daily_pnl` table with composite PK | DDL confirmed. Written by Phase 2 Flight; table created here so schema is stable from day 1. |
| SCHEMA-05 | `MotherDuckLogger` connects via `MOTHERDUCK_TOKEN`, runs `CREATE TABLE IF NOT EXISTS` on startup | `duckdb.connect("md:", config={"motherduck_token": token})` confirmed pattern. |
| SCHEMA-06 | `log_order()` writes to `trades` with `ON CONFLICT (order_id) DO NOTHING` | DuckDB supports this syntax. Critical: do NOT use `DO UPDATE` on the conflict column (DuckDB bug #16698). |
| SCHEMA-07 | `update_fill()` updates submitted trade with fill data | `UPDATE trades SET filled_at=?, filled_avg_price=?, pnl=?, status='filled' WHERE order_id=?`. The `pnl` column is NULLABLE — passing `pnl=None` in Phase 1 is valid per the column definition. |
| SCHEMA-08 | `snapshot_positions()` writes open positions from Alpaca to `positions` | `client.trading.get_all_positions()` returns `List[Position]`. `unrealized_pl` is the field name (not `unrealized_pnl`). |
| SCHEMA-09 | `snapshot_portfolio()` writes account equity/cash to `portfolio_snapshots` | `client.trading.get_account()` returns `TradeAccount`. Fields: `equity`, `cash`, `buying_power` — all Optional[str], cast to float. |
| SCHEMA-10 | Graceful degradation when `MOTHERDUCK_TOKEN` absent | `if token: ... else: pass` pattern — no import-time duckdb side effects. |
| INTEG-01 | `OrderManager` accepts optional `md_logger=None` | Confirmed: existing call sites pass `OrderManager(client=client, logger=logger)` — adding `md_logger=None` is backward-compatible. |
| INTEG-02 | `OrderManager` calls `md_logger.log_order()` after each order submission in all 5 methods | All 5 confirmed: buy, sell, short_sell, buy_to_cover, close_position. `close_position` RETURNS an `Order` (`client.trading.close_position()` -> `Order(**response)`, confirmed in alpaca/trading/client.py:296-324) — capture the return value and call `log_order` on it. |
| INTEG-03 | `runner.py` constructs `MotherDuckLogger` when `MOTHERDUCK_TOKEN` present, passes to `OrderManager` | `os.environ.get("MOTHERDUCK_TOKEN")` check. Import at top of runner.py. |
| INTEG-04 | `runner.py` calls `snapshot_positions()` and `snapshot_portfolio()` after `run_cron()` returns | `run_cron()` is blocking (APScheduler loop). This only fires on process exit. Design decision: call before scheduler starts, or after `run_cron()` returns is only reached on ^C. See pitfall. |
| INTEG-05 | `runner.py` polls Alpaca for fill confirmation after `run_cron()` and calls `update_fill()` | Same timing concern as INTEG-04. Use `client.trading.get_orders()` filtered to today. |
| INTEG-06 | No files under `strategies/` modified | Confirmed: integration is entirely in `core/` and `runner.py`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema DDL (CREATE TABLE) | Python / core layer | MotherDuck (persists) | Run once on logger init; `IF NOT EXISTS` makes it idempotent |
| Order logging (trades table) | `OrderManager` | `MotherDuckLogger` | All 5 order methods are the single choke point for every order |
| Fill polling + update | `runner.py` | `MotherDuckLogger` | runner.py has the event loop context; logger provides the SQL method |
| Position snapshot | `runner.py` | `MotherDuckLogger` | runner.py calls Alpaca for positions; logger writes them |
| Portfolio snapshot | `runner.py` | `MotherDuckLogger` | runner.py calls `get_account()`; logger writes it |
| Graceful degradation | `MotherDuckLogger.__init__` | `runner.py` guard | Token check in runner.py; logger never constructed if absent |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `duckdb` | `==1.5.2` | Python-to-MotherDuck write layer | Only new dependency. MotherDuck extension bundled. Pin exactly for Flight reproducibility. [VERIFIED: pip index versions duckdb] |

### Existing (no change)

| Library | Version | Purpose |
|---------|---------|---------|
| `alpaca-py` | `0.43.4` | Alpaca SDK — `Order`, `Position`, `TradeAccount` models already in venv |
| `python-dotenv` | `1.2.2` | `.env` loading in runner.py |
| `pytest` | already in venv | Test framework for regression tests |

### Installation

```bash
# Add to requirements.txt
duckdb==1.5.2

# Install in venv
.venv/bin/pip install duckdb==1.5.2
```

**Version verification:** `pip index versions duckdb` confirms 1.5.2 is on PyPI. Latest is 1.5.3 — use 1.5.2 per STACK.md recommendation for Flight compatibility. [VERIFIED: pip index versions duckdb]

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `duckdb` | PyPI | ~6 yrs | Very high | github.com/duckdb/duckdb | [OK] | Approved |

**slopcheck result:** `[OK]` for duckdb (ran via venv slopcheck, exit code 1 only because it tried to `pip install` after scanning — the scan itself completed cleanly).

**Packages removed due to [SLOP]:** none
**Packages flagged [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
runner.py
  │
  ├─► os.environ.get("MOTHERDUCK_TOKEN")
  │       │
  │       ├── present → MotherDuckLogger(token)
  │       │                  └─► duckdb.connect("md:", config={token})
  │       │                  └─► _ensure_schema() [CREATE TABLE IF NOT EXISTS x4]
  │       │
  │       └── absent  → md_logger = None
  │
  ├─► OrderManager(client, logger, md_logger=md_logger)
  │
  ├─► strategy_class(client, order_manager, logger, config)
  │
  ├─► run_cron(strategy, client, config_module)   ← BLOCKING
  │       │
  │       └─► strategy.on_bar(bars)
  │               └─► order_manager.buy/sell/etc.
  │                       └─► [if md_logger] md_logger.log_order(order, strategy_name, account_name)
  │
  └─► [after run_cron exits — see INTEG-04 pitfall]
      ├─► client.trading.get_all_positions()
      │       └─► md_logger.snapshot_positions(positions, strategy, account_name)
      ├─► client.trading.get_account()
      │       └─► md_logger.snapshot_portfolio(account, strategy, account_name)
      └─► poll_fills: client.trading.get_orders(today, status=filled)
              └─► md_logger.update_fill(order_id, filled_at, filled_avg_price, pnl)
```

### Recommended Project Structure

```
core/
├── motherduck_logger.py   # NEW — MotherDuckLogger class
├── order_manager.py       # EDIT — add md_logger=None param, call log_order in 5 methods
├── accounts.py            # unchanged
├── alpaca_client.py       # unchanged — add get_all_positions() helper if needed
├── base_strategy.py       # unchanged
├── logger.py              # unchanged
└── scheduler.py           # unchanged
runner.py                  # EDIT — construct logger, pass to OrderManager, call snapshots
requirements.txt           # EDIT — add duckdb==1.5.2
```

### Pattern 1: MotherDuckLogger Class Structure

```python
# core/motherduck_logger.py
# Source: .planning/research/FEATURES.md (confirmed schema)
import os
from datetime import datetime, timezone
import duckdb

class MotherDuckLogger:
    def __init__(self, token: str):
        self.con = duckdb.connect("md:", config={"motherduck_token": token})
        self._ensure_schema()

    def _ensure_schema(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.trades (
                order_id         VARCHAR PRIMARY KEY,
                strategy_name    VARCHAR NOT NULL,
                account_name     VARCHAR NOT NULL,
                symbol           VARCHAR NOT NULL,
                side             VARCHAR NOT NULL,
                qty              DECIMAL(18,4) NOT NULL,
                submitted_at     TIMESTAMPTZ NOT NULL,
                filled_at        TIMESTAMPTZ,
                filled_avg_price DECIMAL(18,4),
                pnl              DECIMAL(18,4),
                status           VARCHAR NOT NULL DEFAULT 'submitted'
            )
        """)
        # positions, portfolio_snapshots, daily_pnl tables follow same pattern

    def log_order(self, order, strategy_name: str, account_name: str):
        if order is None:
            return
        self.con.execute("""
            INSERT INTO trading.main.trades
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'submitted')
            ON CONFLICT (order_id) DO NOTHING
        """, [
            str(order.id), strategy_name, account_name,
            order.symbol, str(order.side.value),
            float(order.qty), order.submitted_at
        ])

    def update_fill(self, order_id: str, filled_at: datetime,
                    filled_avg_price: float, pnl: float):
        self.con.execute("""
            UPDATE trading.main.trades
            SET filled_at = ?, filled_avg_price = ?, pnl = ?, status = 'filled'
            WHERE order_id = ?
        """, [filled_at, filled_avg_price, pnl, order_id])
```

### Pattern 2: OrderManager Integration

```python
# core/order_manager.py — minimal edit
class OrderManager:
    def __init__(self, client, logger, md_logger=None):  # md_logger=None is new
        self.client = client
        self.logger = logger
        self.md_logger = md_logger
        # strategy_name and account_name must be injected for log_order
        # Two options: (A) pass to __init__, (B) pass to each log_order call
        # Option B is cleaner — runner.py knows both values

    def buy(self, symbol: str, qty: float):
        try:
            order = self.client.trading.submit_order(...)
            self.logger.info(f"BUY submitted order_id={order.id}")
            # NEW: md_logger call  — strategy_name/account_name passed from caller
            # See pitfall below for how to get strategy_name into OrderManager
            return order
        except Exception as e:
            self.logger.error(...)
            return None
```

**Critical design decision for INTEG-02:** `log_order` needs `strategy_name` and
`account_name`, but `OrderManager` currently has no knowledge of which strategy is
using it. Two approaches:

- **Option A (recommended):** Pass `strategy_name` and `account_name` to `OrderManager.__init__`.
  `runner.py` knows both (`args.strategy` and `account_for(args.strategy)`). Clean; no
  interface change for callers that pass `md_logger=None`.
- **Option B:** Pass `strategy_name`/`account_name` to each `log_order()` call inside
  each order method — requires caller to provide them, but `OrderManager` doesn't have
  them directly.

Option A is simpler: `OrderManager(client=client, logger=logger, md_logger=md_logger, strategy_name=args.strategy, account_name=account_for(args.strategy))`. Existing tests pass `OrderManager(client=client, logger=logger)` — both new params default to empty string or None, no breaking change.

### Pattern 3: runner.py Integration

```python
# runner.py — additions to main()
import os
from core.accounts import account_for
# NEW import:
# from core.motherduck_logger import MotherDuckLogger

token = os.environ.get("MOTHERDUCK_TOKEN")
md_logger = MotherDuckLogger(token) if token else None

account_name = account_for(args.strategy)
order_manager = OrderManager(
    client=client, logger=logger, md_logger=md_logger,
    strategy_name=args.strategy, account_name=account_name
)

# ... strategy construction, then:
if args.trigger == "cron":
    run_cron(strategy, client, config_module)
else:
    run_stream(strategy, client, config_module)

# Snapshots and fill poll — only reachable after scheduler exits (see INTEG-04 pitfall)
if md_logger:
    _snapshot_and_poll(client, md_logger, args.strategy, account_name)
```

### Pattern 4: Alpaca SDK Field Access

Alpaca model fields confirmed from SDK source:

```python
# Order fields (all confirmed from alpaca/trading/models.py)
str(order.id)              # UUID — convert to str for VARCHAR PK
order.symbol               # str
str(order.side.value)      # "buy" or "sell" — .value extracts string from enum
float(order.qty)           # qty is str or float from SDK — cast to float
order.submitted_at         # datetime (timezone-aware)
order.filled_at            # Optional[datetime]
float(order.filled_avg_price) if order.filled_avg_price else None  # Optional[str|float]

# Position fields
position.symbol            # str
float(position.qty)        # str in SDK — cast to float
float(position.avg_entry_price)   # str — cast
float(position.current_price) if position.current_price else None  # Optional[str]
float(position.unrealized_pl) if position.unrealized_pl else None  # field name is unrealized_pl NOT unrealized_pnl

# TradeAccount fields
float(account.equity) if account.equity else None    # Optional[str] — cast
float(account.cash) if account.cash else None        # Optional[str] — cast
float(account.buying_power) if account.buying_power else None  # Optional[str] — cast
```

### Anti-Patterns to Avoid

- **Ignoring the `close_position` return value:** `order_manager.close_position()` calls `client.trading.close_position(symbol)`, which RETURNS an `Order` (`Order(**response)`, confirmed in alpaca/trading/client.py:296-324). The current code discards this return value. Capture it (`order = self.client.trading.close_position(symbol)`) and call `log_order(order, ...)` — close_position is the 5th order-logging site per INTEG-02.
- **`DO UPDATE` on conflict column:** Do NOT use `ON CONFLICT (order_id) DO UPDATE SET order_id = excluded.order_id` — DuckDB bug #16698 corrupts the row. Use `DO NOTHING` only.
- **Importing duckdb at module top-level when token absent:** If `import duckdb` is at the top of `motherduck_logger.py`, it runs even when no token is present. This is fine (duckdb is a regular import), but the `MotherDuckLogger` class must only be instantiated when the token is present.
- **Assuming `run_cron()` returns on a normal run:** `run_cron()` starts a `BlockingScheduler` which runs indefinitely. Snapshots and fill poll placed after it only execute on process exit (SIGINT/SIGTERM). See pitfall 1 below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent insert | Custom dedupe logic | `INSERT ... ON CONFLICT (order_id) DO NOTHING` | DuckDB native; one line |
| Schema migration | Version tracking / migration scripts | `CREATE TABLE IF NOT EXISTS` | Sufficient for this milestone; tables are append-only |
| Connection pooling | Custom connection manager | Single `duckdb.connect()` held on instance | DuckDB connections are not thread-safe but runner.py is single-threaded; one connection per process is correct |
| P&L calculation | Complex position tracking | Compute at fill time: `pnl = (filled_avg_price - avg_entry_price) * qty * direction` | Simple formula; done in Python where all data is available |

**Key insight:** The integration surface is intentionally tiny. All complexity is in MotherDuck, not in Python. Keep the logger class under ~100 lines.

## Common Pitfalls

### Pitfall 1: `run_cron()` blocks forever — snapshots never called
**What goes wrong:** `run_cron()` starts APScheduler's `BlockingScheduler.start()`, which
is an infinite loop. Code after `run_cron(strategy, client, config_module)` in `runner.py`
is only reached when the process is killed (SIGINT/SIGTERM). This means snapshots and fill
polls placed after `run_cron()` only execute at shutdown, not after each bar.
**Why it happens:** Intended design — scheduler loops until killed. But INTEG-04 and
INTEG-05 say "after `run_cron()` returns".
**How to avoid:** Two valid interpretations:
1. **At shutdown** (simplest): Wrap snapshot/poll in a `try/finally` around `run_cron()`.
   On SIGINT, finally block runs. This is fine for GitHub Actions (job ends, GH kills the process).
2. **Inside the cron job**: Move snapshot/poll into a wrapper that `run_cron` calls after
   each `strategy.on_bar()`. Requires touching `scheduler.py`.
**Recommendation:** Use `try/finally` in `runner.py`. Matches the INTEG-04/05 requirement
wording ("after `run_cron()` returns") and keeps `scheduler.py` untouched.
**Warning signs:** Tests show snapshot rows in DB after each run — but if no rows appear
until process exit, that's expected and correct with the try/finally approach.

### Pitfall 2: Alpaca numeric fields are strings, not floats
**What goes wrong:** `Order.qty`, `Position.qty`, `TradeAccount.equity` etc. are
`Optional[str]` or `Optional[Union[str, float]]` in the SDK. Inserting a string "1.0"
into a `DECIMAL(18,4)` column may work in DuckDB via implicit cast, but P&L arithmetic
will fail silently if done in Python without casting first.
**How to avoid:** Always `float(x)` before arithmetic or insertion. Guard with
`float(x) if x is not None else None`.

### Pitfall 3: `order.side` is an enum, not a string
**What goes wrong:** `Order.side` is `Optional[OrderSide]` enum. Inserting it directly
stores `<OrderSide.BUY: 'buy'>` string representation, not `'buy'`.
**How to avoid:** `str(order.side.value)` extracts the string value from the enum.

### Pitfall 4: Missing `strategy_name`/`account_name` on `OrderManager`
**What goes wrong:** Logger needs both fields to write meaningful rows, but `OrderManager`
currently has no concept of which strategy uses it.
**How to avoid:** Pass `strategy_name` and `account_name` to `OrderManager.__init__` in
`runner.py`. Default both to `""` or `None` so existing test code (`OrderManager(client=client, logger=_NullLogger())`) keeps working without changes.

### Pitfall 5: `get_all_positions()` not on `AlpacaClient` wrapper
**What goes wrong:** `core/alpaca_client.py` wraps the SDK but does not expose
`get_all_positions()`. `runner.py` would need to call `client.trading.get_all_positions()`
directly, bypassing the wrapper.
**How to avoid:** Either call `client.trading.get_all_positions()` directly in `runner.py`
(acceptable — it's not trading logic, just data retrieval), or add a thin wrapper method
to `AlpacaClient`. The former is simpler and doesn't touch `alpaca_client.py`.

## Code Examples

Verified patterns from codebase inspection and SDK source:

### DuckDB Connection to MotherDuck
```python
# Source: .planning/research/STACK.md (confirmed authoritative via MotherDuck MCP tools)
import duckdb
con = duckdb.connect("md:", config={"motherduck_token": token})
# OR if MOTHERDUCK_TOKEN is already in env:
con = duckdb.connect("md:")
```

### Parameterized INSERT with ON CONFLICT
```python
# Source: .planning/research/FEATURES.md + DuckDB docs
con.execute("""
    INSERT INTO trading.main.trades
        (order_id, strategy_name, account_name, symbol, side, qty, submitted_at, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted')
    ON CONFLICT (order_id) DO NOTHING
""", [str(order.id), strategy_name, account_name,
      order.symbol, str(order.side.value),
      float(order.qty), order.submitted_at])
```

### Graceful degradation in runner.py
```python
# runner.py — before OrderManager construction
token = os.environ.get("MOTHERDUCK_TOKEN")
md_logger = None
if token:
    from core.motherduck_logger import MotherDuckLogger
    md_logger = MotherDuckLogger(token)
```

### Snapshot + fill poll with try/finally
```python
# runner.py — wrapping run_cron
try:
    run_cron(strategy, client, config_module)
finally:
    if md_logger:
        positions = client.trading.get_all_positions()
        md_logger.snapshot_positions(positions, args.strategy, account_name)
        account = client.trading.get_account()
        md_logger.snapshot_portfolio(account, args.strategy, account_name)
        # poll fills
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        import datetime
        today = datetime.date.today()
        orders = client.trading.get_orders(GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=datetime.datetime.combine(today, datetime.time.min, tzinfo=datetime.timezone.utc)
        ))
        for o in orders:
            if o.filled_at and o.filled_avg_price:
                # pnl=None in Phase 1 — trades.pnl column is nullable (SCHEMA-07);
                # realized P&L is computed by the Phase 2 daily_pnl aggregation Flight
                md_logger.update_fill(str(o.id), o.filled_at, float(o.filled_avg_price), None)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Local file logging only | MotherDuck cloud writes | This phase | All trades observable in SQL |
| No idempotency | `ON CONFLICT DO NOTHING` | DuckDB 1.x | Safe for CI re-runs |
| — | `TIMESTAMPTZ` for all timestamps | From day 1 | Correct DST-aware aggregation |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `trading` database should be created if it doesn't exist, or already exists in MotherDuck | Schema patterns | If DB doesn't auto-create, need `CREATE DATABASE IF NOT EXISTS trading` before table DDL |
| A2 | `duckdb==1.5.2` is compatible with the current MotherDuck service | Standard Stack | If MD requires 1.5.3, pin would need to change |
| A3 | pnl at fill time = `(filled_avg_price - avg_entry_price) * qty * side_sign` | Pattern 3 / INTEG-05 | If pnl semantics differ (e.g. for short positions), P&L values will be wrong |
| A4 | `run_cron()` returns on SIGINT (try/finally fires before process dies) | Pitfall 1 | If GH Actions sends SIGKILL, finally block never runs and snapshots are lost |

## Open Questions

> All open questions RESOLVED 2026-06-03 during plan revision (confirmed against SDK source and REQUIREMENTS.md).

1. **Does MotherDuck auto-create the `trading` database on first `CREATE TABLE IF NOT EXISTS`?**
   - **RESOLVED:** `CREATE DATABASE IF NOT EXISTS trading` is the confirmed approach. `_ensure_schema()` runs it as its first statement before any `CREATE TABLE IF NOT EXISTS trading.main.<table>`. Harmless if the database already exists, and it makes the same DDL valid both against MotherDuck and against an in-memory DuckDB connection used in tests.
   - What we knew: `duckdb.connect("md:")` connects to the account. The schema DDL uses `trading.main.trades`.

2. **P&L computation: what data is available at fill time?**
   - **RESOLVED:** Store `pnl = None` in `update_fill()` for Phase 1. This is valid because the `trades.pnl` column is NULLABLE per SCHEMA-07 — no requirement amendment is needed. The Phase 2 `daily_pnl` aggregation Flight computes realized P&L from filled trade rows; Phase 1 only records the raw fill (`filled_at`, `filled_avg_price`, `status='filled'`).
   - What we knew: INTEG-05 says compute `pnl` when polling fills. To compute realized P&L you need `avg_entry_price`, which is not in the `trades` table; deferring to the Phase 2 aggregation is the clean split.

3. **`close_position` — should it be logged?**
   - **RESOLVED:** YES — `close_position` RETURNS an `Order`. `client.trading.close_position(symbol)` is declared `-> Union[Order, RawData]` and its body ends with `return Order(**response)` (confirmed in `.venv/lib/python3.14/site-packages/alpaca/trading/client.py:296-324`). `OrderManager.close_position` must capture the return value (`order = self.client.trading.close_position(symbol)`) and call `self.md_logger.log_order(order, ...)`. This is the 5th log_order site required by INTEG-02 ("all 5 order methods").
   - What we knew: INTEG-02 explicitly lists all 5 order methods, including `close_position`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All code | ✓ | 3.14.5 | — |
| `.venv` (project virtualenv) | Package installs | ✓ | active | — |
| `duckdb==1.5.2` | MotherDuckLogger | ✗ | not installed | Install via pip |
| `alpaca-py` | Order/Position models | ✓ | 0.43.4 | — |
| `pytest` | Test suite | ✓ | in venv | — |
| `MOTHERDUCK_TOKEN` env var | Live MotherDuck writes | unknown | — | Logger not constructed; local runs unaffected |

**Missing dependencies with no fallback:**
- `duckdb==1.5.2` — must be installed before any MotherDuck write can happen

**Missing dependencies with fallback:**
- `MOTHERDUCK_TOKEN` — absent token means logger is never constructed; all existing behavior preserved (SCHEMA-10)

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (in venv) |
| Config file | none — pytest auto-discovers |
| Quick run command | `.venv/bin/python -m pytest tests/test_live_execution.py -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-10 | Logger degrades when token absent | unit | `pytest tests/test_motherduck_logger.py::test_no_token_no_exception -x` | ❌ Wave 0 |
| SCHEMA-06 | `ON CONFLICT DO NOTHING` — same order twice = one row | unit | `pytest tests/test_motherduck_logger.py::test_idempotent_insert -x` | ❌ Wave 0 |
| INTEG-01 | OrderManager backward compat — no md_logger still works | unit | `pytest tests/test_live_execution.py -q` | ✅ existing |
| INTEG-02 | `log_order` called after each of 5 order methods | unit | `pytest tests/test_order_manager_logging.py -x` | ❌ Wave 0 |
| INTEG-06 | No strategy file modified | smoke | `git diff --name-only HEAD strategies/` | manual |

### Wave 0 Gaps

- [ ] `tests/test_motherduck_logger.py` — unit tests for MotherDuckLogger using in-memory DuckDB (`duckdb.connect()` without `"md:"`) to test schema creation, log_order idempotency, update_fill, snapshot_positions, snapshot_portfolio, graceful degradation
- [ ] `tests/test_order_manager_logging.py` — tests that `md_logger.log_order()` is called (mock logger) for all 5 order methods (including close_position, which returns an Order), and that existing tests pass when `md_logger=None`

**Key test strategy:** Use `duckdb.connect()` (in-memory) instead of `duckdb.connect("md:")` in tests. `MotherDuckLogger` should accept either a real connection or allow injection for testing. Pattern: pass connection in constructor for tests, or use env var to select in-memory mode.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `MOTHERDUCK_TOKEN` from env var only — never hardcoded |
| V3 Session Management | no | Single-process, no sessions |
| V4 Access Control | no | Internal Python module |
| V5 Input Validation | yes | All Alpaca values cast via `float()` before insert; parameterized queries prevent injection |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token in source code | Information Disclosure | `os.environ.get("MOTHERDUCK_TOKEN")` only; never committed |
| SQL injection via order data | Tampering | Parameterized queries (`?` placeholders) for all DuckDB execute calls |
| Token in logs | Information Disclosure | Logger only logs strategy name and order IDs, never token |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `core/order_manager.py`, `runner.py`, `core/alpaca_client.py`, `core/scheduler.py` — direct source of truth for integration points
- `.venv/lib/python3.14/site-packages/alpaca/trading/models.py` — confirmed Alpaca `Order`, `Position`, `TradeAccount` field names and types
- `.venv/lib/python3.14/site-packages/alpaca/trading/client.py:296-324` — confirmed `close_position()` returns `Union[Order, RawData]` and builds `Order(**response)` (Open Question 3)
- `.planning/research/FEATURES.md` — authoritative schema DDL (researched via MotherDuck MCP tools 2026-06-03)
- `.planning/research/ARCHITECTURE.md` — integration patterns (researched via MotherDuck MCP tools 2026-06-03)
- `.planning/research/STACK.md` — duckdb version, connection pattern
- `.planning/research/PITFALLS.md` — critical pitfalls including DuckDB bug #16698

### Secondary (MEDIUM confidence)
- `pip index versions duckdb` — confirmed 1.5.2 is on PyPI [VERIFIED: pip registry]

### Tertiary (LOW confidence)
- A1: `trading` DB auto-creation behavior — resolved by adding `CREATE DATABASE IF NOT EXISTS trading` as the first DDL statement (see Open Question 1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — duckdb 1.5.2 confirmed on PyPI, existing deps confirmed in venv
- Architecture: HIGH — integration points confirmed by direct codebase inspection
- Alpaca models: HIGH — confirmed from SDK source in installed venv (including close_position return type)
- Pitfalls: HIGH — sourced from authoritative prior research + codebase evidence

**Research date:** 2026-06-03
**Valid until:** 2026-09-01 (stable tech; duckdb version pin may need update for Flight compat)
